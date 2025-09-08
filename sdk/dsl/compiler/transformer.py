# compiler/transformer.py
from __future__ import annotations

import logging
import re
from typing import Dict, List, Tuple, Optional, Any, Iterable
from lark import Transformer, Tree, v_args, Token

from dsl.compiler.validator import validate_mission_ir
from dsl.compiler.ir import MissionIR, ActionIR, EventIR, DatumIR
from dsl.compiler.resolver import resolve_symbols
from dsl.compiler.loader import load_all, print_report

logger = logging.getLogger(__name__)

_DONE_EVENT = "done"
_TERMINATE_AID = "terminate"
_TERMINATE = None

# ---------- Helpers ----------
def _duration_to_seconds(tok: str) -> int:
    tok = tok.strip()
    if tok.endswith(("s", "sec")):
        num = tok[:-1] if tok.endswith("s") else tok[:-3]
        return int(float(num))
    if tok.endswith(("m", "min")):
        num = tok[:-1] if tok.endswith("m") else tok[:-3]
        return int(float(num) * 60)
    return int(float(tok))


def _pairs_to_dict(attrs: Optional[Iterable[Any]]) -> Dict[str, Any]:
    if attrs is None:
        return {}
    if isinstance(attrs, dict):
        return dict(attrs)
    pairs = []
    for it in attrs:
        if isinstance(it, tuple) and len(it) == 2 and isinstance(it[0], str):
            pairs.append(it)
    return dict(pairs)

@v_args(inline=True)
class DroneDSLTransformer(Transformer):
    """Parses DSL -> validates via validator.py -> builds IR. Supports implicit 'done' transitions."""
    def __init__(self):
        super().__init__()
        self._actions: Dict[str, ActionIR] = {}
        self._events: Dict[str, EventIR] = {}
        self._data: Dict[str, DatumIR] = {}
        self._start_aid: Optional[str] = None
        self._during: Dict[str, Dict[str, str]] = {}


    # ----- Attributes -----
    def attr(self, k: Token, _colon, v):
        return (str(k), v)
    
    def array(self, *items):
        return [it for it in items if not isinstance(it, Token)]

    def value(self, v):
        if isinstance(v, Tree):
            if v.data == 'array':
                return [self.value(child) for child in v.children if not isinstance(child, Token)]
            return v
        if isinstance(v, Token):
            t = v.type
            s = str(v)
            if t == "DURATION":
                return _duration_to_seconds(s)
            if t == "NUMBER":
                f = float(s); return int(f) if f.is_integer() else f
            if t == "STRING":
                return s[1:-1] if s and s[0]==s[-1] and s[0] in ("'", '"') else s
            if t == "NAME":
                return s
        return v

    # ----- Actions -----
    def action_decl(self, type_name: Token, action_id: Token, attrs: Optional[List] = None):
        type_str = str(type_name)
        aid = str(action_id)
        attrs_dict = _pairs_to_dict(attrs)
        self._actions[aid] = ActionIR(type_name=type_str, action_id=aid, attributes=attrs_dict)
        logger.debug("action_decl: %s (%s) attrs=%s", aid, type_str, attrs_dict)

    def action_body(self, *items):
        return [it for it in items if isinstance(it, tuple) and len(it) == 2]

    # ----- Events -----
    def event_decl(self, type_name: Token, event_name: Token, attrs: Optional[List] = None):
        type_str = str(type_name)
        eid = str(event_name)
        attrs_dict = _pairs_to_dict(attrs)
        self._events[eid] = EventIR(type_name=type_str, event_name=eid, attributes=attrs_dict)
        logger.debug("event_decl: %s (%s) attrs=%s", eid, type_str, attrs_dict)

    def event_body(self, *items):
        return [it for it in items if isinstance(it, tuple) and len(it) == 2]
    
    # ----- Data -----
    def Datum_decl(self, type_name: Token, datum_id: Token, attrs: Optional[List] = None):
        t = str(type_name); mid = str(datum_id)
        attrs_dict = _pairs_to_dict(attrs)
        self._data[mid] = DatumIR(type_name=t, datum_id=mid, attributes=attrs_dict)
        logger.debug("message_decl: %s (%s) attrs=%s", mid, t, attrs_dict)

    def message_body(self, *items):
        return [it for it in items if isinstance(it, tuple) and len(it) == 2]

    # ----- Mission / transitions (unchanged) -----

    def start(self, *children):
        logger.info("transform: building MissionIR (actions=%d, events=%d, messages=%d)",
                    len(self._actions), len(self._events), len(self._data))
        transitions: Dict[Tuple[str, str], str] = {}

        for aid, evmap in self._during.items():
            for eid, nxt_aid in evmap.items():
                transitions[(aid, eid)] = nxt_aid
            if _DONE_EVENT not in evmap:
                transitions[(aid, _DONE_EVENT)] = _TERMINATE_AID

        mir = MissionIR(
            actions=self._actions,
            events=self._events,
            messages=self._data,     # ← NEW
            start_action_id=self._start_aid,
            transitions=transitions,
        )

        # Scan your SDK so @register_* have run.
        # With your current tree, messages live under 'sdk.api.messages'
        load_all("sdk.api", force=True, show_trace=False)
        # (optional) print_report(load_all(...)) if you want a summary

        mir = resolve_symbols(mir)
        mir = validate_mission_ir(mir)
        logger.info("transform: done (transitions=%d)", len(transitions))
        return mir
    
    # ----- Mission -----
    def mission_start(self, action_id: Token):
        self._start_aid = str(action_id)
        logger.info("mission_start: %s", self._start_aid)

    def transition_body(self, *items):
        return [it for it in items if isinstance(it, tuple) and len(it) == 2]

    def transition_rule(self, eid: Token, _arrow, nxt_aid: Token, *_nl):
        rule = (str(eid), str(nxt_aid))
        logger.debug("transition_rule: %s -> %s", rule[0], rule[1])
        return rule

    def during_block(self, action_id: Token, _nl, rules_list):
        aid = str(action_id)
        self._during.setdefault(aid, {})
        for eid, nxt_aid in rules_list:
            self._during[aid][eid] = nxt_aid
        logger.debug("during_block: %s rules=%s", aid, self._during[aid])

    def mission_block(self, *_children):
        return None

    # ----- Top-level -----
    def start(self, *children):
        logger.info("transform: building MissionIR (actions=%d, events=%d)",
                    len(self._actions), len(self._events))
        transitions: Dict[Tuple[str, str], str] = {}
        implicit_done_added = 0

        for aid, evmap in self._during.items():
            for eid, nxt_aid in evmap.items():
                transitions[(aid, eid)] = nxt_aid
            if _DONE_EVENT not in evmap:  # implicit done transition
                transitions[(aid, _DONE_EVENT)] = _TERMINATE_AID
                implicit_done_added += 1

        if implicit_done_added:
            logger.info("transform: added %d implicit 'done' -> terminate transitions",
                        implicit_done_added)

        mir = MissionIR(
            actions=self._actions,
            events=self._events,
            start_action_id=self._start_aid,
            transitions=transitions
        )

        # Ensure SDK is loaded (registrations happen at import-time)
        logger.info("loader: scanning SDK modules...")
        summaries = load_all(force=True, show_trace=False)
        print_report(summaries)  # uses logging internally

        logger.info("resolver: resolving symbol references")
        mir = resolve_symbols(mir)

        logger.info("validator: validating MissionIR")
        mir = validate_mission_ir(mir)

        logger.info("transform: done (transitions=%d)", len(transitions))
        return mir
