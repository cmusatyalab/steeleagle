# compiler/transformer.py
from __future__ import annotations

import logging
from typing import Dict, List, Tuple, Optional, Any, Iterable
from lark import Transformer, Tree, v_args, Token

from ..dsl.compiler.validator import validate_mission_ir
from ..dsl.compiler.ir import MissionIR, ActionIR, EventIR, DatumIR
from ..dsl.compiler.resolver import resolve_symbols
from ..dsl.compiler.loader import load_all, print_report

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
    """
    Parses DSL -> loads SDK registries -> resolves symbol references -> validates IR.
    Supports:
      - Top-level Data section
      - Inline data constructors inside Actions and Events
      - Implicit 'done' -> terminate transitions
    """
    def __init__(self):
        super().__init__()
        self._actions: Dict[str, ActionIR] = {}
        self._events: Dict[str, EventIR] = {}
        self._data: Dict[str, DatumIR] = {}
        self._start_aid: Optional[str] = None
        self._during: Dict[str, Dict[str, str]] = {}

    # ===== Data =====
    def datum_decl(self, type_name: Token, datum_id: Token, attrs: Optional[List] = None):
        t = str(type_name)
        did = str(datum_id)
        attrs_dict = _pairs_to_dict(attrs)
        self._data[did] = DatumIR(type_name=t, datum_id=did, attributes=attrs_dict)
        logger.debug("data_decl: %s (%s) attrs=%s", did, t, attrs_dict)

    def datum_body(self, *items):
        # Data block does NOT allow inline constructors inside; this just returns k/v pairs
        return [it for it in items if isinstance(it, tuple) and len(it) == 2]

    # ===== Actions =====
    def action_decl(self, type_name: Token, action_id: Token, attrs: Optional[List] = None):
        type_str = str(type_name)
        aid = str(action_id)
        attrs_dict = _pairs_to_dict(attrs)
        self._actions[aid] = ActionIR(type_name=type_str, action_id=aid, attributes=attrs_dict)
        logger.debug("action_decl: %s (%s) attrs=%s", aid, type_str, attrs_dict)

    def action_body(self, *items):
        # Uses ae_attr (allows inline data in actions/events)
        return [it for it in items if isinstance(it, tuple) and len(it) == 2]

    # ===== Events =====
    def event_decl(self, type_name: Token, event_name: Token, attrs: Optional[List] = None):
        type_str = str(type_name)
        eid = str(event_name)
        attrs_dict = _pairs_to_dict(attrs)
        self._events[eid] = EventIR(type_name=type_str, event_name=eid, attributes=attrs_dict)
        logger.debug("event_decl: %s (%s) attrs=%s", eid, type_str, attrs_dict)

    def event_body(self, *items):
        # Uses ae_attr (allows inline data in actions/events)
        return [it for it in items if isinstance(it, tuple) and len(it) == 2]

    # ===== Attributes / Values =====
    def attr(self, k: Token, _sep, v):
        # Data block only. Because ?value is inlined in the grammar, `value()` may
        # not be called by Lark — normalize here.
        def _norm(x):
            if isinstance(x, Token):
                return self.value(x)          # NUMBER/STRING/NAME/DURATION -> py value
            if isinstance(x, Tree):
                return self.value(x)          # arrays etc.
            if isinstance(x, list):
                return [_norm(it) for it in x]
            if isinstance(x, dict):
                return {kk: _norm(vv) for kk, vv in x.items()}
            return x
        return (str(k), _norm(v))

    def ae_attr(self, k, _sep, v):
        return (str(k), v)

    def ae_value(self, v):
        # Reuse your existing normalization for NUMBER/STRING/NAME/DURATION/arrays
        return self.value(v)

    def ae_array(self, *items):
        return [it for it in items if not isinstance(it, Token)]

    def datum_kwarg(self, k, _sep, v):
        # k: NAME, v: already normalized (ae_value path)
        return (str(k), v)

    def datum_args(self, *items):
        """
        Children come from either:
        - datum_kwarg items -> already (k, v) tuples, or
        - ae_value items -> may be plain python OR raw Token if not yet normalized.
        convert Tokens with self.value().
        """
        out = []
        for it in items:
            if isinstance(it, Token):
                # Ignore punctuation, convert real values
                if it.type in ("COMMA", "LPAREN", "RPAREN"):
                    continue
                out.append(self.value(it))
            else:
                out.append(it)
        return out

    def datum_inline(self, type_name, *args):
        tname = str(type_name)
        # Drop stray punctuation
        args_clean = [a for a in args if not isinstance(a, Token)]

        if not args_clean:
            return {"__inline__": True, "type": tname, "args": [], "kwargs": {}}

        args0 = args_clean[0]
        # Named form: list of (k, v)
        if isinstance(args0, list) and args0 and isinstance(args0[0], tuple) and len(args0[0]) == 2:
            return {"__inline__": True, "type": tname, "args": [], "kwargs": {k: v for (k, v) in args0}}

        # Positional form: list of values
        if isinstance(args0, list):
            return {"__inline__": True, "type": tname, "args": args0, "kwargs": {}}

        # Single positional value
        return {"__inline__": True, "type": tname, "args": [args0], "kwargs": {}}
    def value(self, v):
        # General values for Data block (no inline production reaches here)
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
                return s[1:-1] if s and s[0] == s[-1] and s[0] in ("'", '"') else s
            if t == "NAME":
                return s
        return v

    # ===== Mission / transitions =====
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

    # ===== Top-level =====
    def start(self, *children):
        logger.info(
            "transform: building MissionIR (actions=%d, events=%d, data=%d)",
            len(self._actions), len(self._events), len(self._data)
        )
        transitions: Dict[Tuple[str, str], str] = {}
        implicit_done_added = 0

        for aid, evmap in self._during.items():
            for eid, nxt_aid in evmap.items():
                transitions[(aid, eid)] = nxt_aid
            if _DONE_EVENT not in evmap:
                transitions[(aid, _DONE_EVENT)] = _TERMINATE_AID
                implicit_done_added += 1

        if implicit_done_added:
            logger.info("transform: added %d implicit 'done' -> terminate transitions",
                        implicit_done_added)

        mir = MissionIR(
            actions=self._actions,
            events=self._events,
            data=self._data,
            start_action_id=self._start_aid,
            transitions=transitions
        )

        # Import API so @register_* hooks populate registries
        summaries = load_all("api", force=True, show_trace=False)
        print_report(summaries)

        logger.info("resolver: resolving symbol references")
        mir = resolve_symbols(mir)

        logger.info("validator: validating MissionIR")
        mir = validate_mission_ir(mir)

        logger.info("transform: done (transitions=%d)", len(transitions))
        logger.info("transform: MissionIR: %s", mir)
        return mir
