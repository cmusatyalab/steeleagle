from __future__ import annotations

import re
from typing import Dict, List, Tuple, Optional, Any, Iterable
from lark import Transformer, Tree, v_args, Token

from compiler.validator import validate_mission_ir
from compiler.ir import MissionIR, ActionIR, EventIR
from compiler.resolver import resolve_symbols
from compiler.loader import load_all


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
        self._start_aid: Optional[str] = None
        self._during: Dict[str, Dict[str, str]] = {}

    # ----- Actions -----
    def action_decl(self, type_name: Token, action_id: Token, attrs: Optional[List] = None):
        type_str = str(type_name)
        aid = str(action_id)
        attrs_dict = _pairs_to_dict(attrs)
        # Defer validation: store raw attrs
        self._actions[aid] = ActionIR(type_name=type_str, action_id=aid, attributes=attrs_dict)

    def action_body(self, *items):
        return [it for it in items if isinstance(it, tuple) and len(it) == 2]

    # ----- Events -----
    def event_decl(self, type_name: Token, event_name: Token, attrs: Optional[List] = None):
        type_str = str(type_name)
        eid = str(event_name)
        attrs_dict = _pairs_to_dict(attrs)
        # Defer validation: store raw attrs
        self._events[eid]=EventIR(type_name=type_str, event_name=eid, attributes=attrs_dict)


    def event_body(self, *items):
        return [it for it in items if isinstance(it, tuple) and len(it) == 2]

    # ----- Attributes -----
    def attr(self, k: Token, _colon, v):
        return (str(k), v)
    
    def array(self, *items):
        # Keep only already-transformed VALUES; drop punctuation tokens
        return [it for it in items if not isinstance(it, Token)]

    def value(self, v):
        # (keep your existing logic)
        if isinstance(v, Tree):
            if v.data == 'array':
                # also filter tokens here, belt-and-suspenders
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

    # ----- Mission -----
    def mission_start(self, action_id: Token):
        self._start_aid = str(action_id)

    def transition_body(self, *items):
        return [it for it in items if isinstance(it, tuple) and len(it) == 2]

    def transition_rule(self, eid: Token, _arrow, nxt_aid: Token, *_nl):
        return (str(eid), str(nxt_aid))

    def during_block(self, action_id: Token, _nl, rules_list):
        aid = str(action_id)
        self._during.setdefault(aid, {})
        for eid, nxt_aid in rules_list:
            self._during[aid][eid] = nxt_aid

    def mission_block(self, *_children):
        return None

    # ----- Top-level -----
    def start(self, *children):
        transitions: Dict[Tuple[str, str], str] = {}

        for aid, evmap in self._during.items():
            for eid, nxt_aid in evmap.items():
                transitions[(aid, eid)] = nxt_aid
            if _DONE_EVENT not in evmap: #implicit done transition
                transitions[(aid, _DONE_EVENT)] = _TERMINATE_AID

        mir = MissionIR(
            actions=self._actions,
            events=self._events,
            start_action_id=self._start_aid,
            transitions=transitions
        )

        load_all()  # Ensure all actions/events are loaded before validation

        mir = resolve_symbols(mir)  # Resolve string references (IDs) into nested dicts
        
        mir = validate_mission_ir(mir) # Validate & normalize via Pydantic (centralized in validator.py)
        return mir
