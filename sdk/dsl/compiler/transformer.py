# compiler/transformer.py
from __future__ import annotations

import logging
from typing import Dict, List, Tuple, Optional, Any, Iterable
from lark import Transformer, Tree, v_args, Token

from ...dsl.compiler import validator
from ...dsl.compiler.ir import MissionIR, ActionIR, EventIR, DatumIR
from ...dsl.compiler import resolver
from ...dsl.compiler import loader

logger = logging.getLogger(__name__)

_DONE_EVENT = "done"
_TERMINATE_AID = "terminate"

# ---------- Helpers ----------

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
        type_str = str(type_name)
        did = str(datum_id)
        attrs_dict = _pairs_to_dict(attrs)
        self._data[did] = DatumIR(type_name=type_str, datum_id=did, attributes=attrs_dict)

    def datum_body(self, *items):
        # filter for attr tuples
        return [it for it in items if isinstance(it, tuple) and len(it) == 2]

    # ===== Actions =====
    def action_decl(self, type_name: Token, action_id: Token, attrs: Optional[List] = None):
        type_str = str(type_name)
        aid = str(action_id)
        attrs_dict = _pairs_to_dict(attrs)
        self._actions[aid] = ActionIR(type_name=type_str, action_id=aid, attributes=attrs_dict)

    def action_body(self, *items):
        return [it for it in items if isinstance(it, tuple) and len(it) == 2]

    # ===== Events =====
    def event_decl(self, type_name: Token, event_id: Token, attrs: Optional[List] = None):
        type_str = str(type_name)
        eid = str(event_id)
        attrs_dict = _pairs_to_dict(attrs)
        self._events[eid] = EventIR(type_name=type_str, event_id=eid, attributes=attrs_dict)

    def event_body(self, *items):
        return [it for it in items if isinstance(it, tuple) and len(it) == 2]

    # ===== Mission / transitions =====
    def mission_start(self, mission_start_kw, action_id, *_nl):
        self._start_aid = str(action_id)
        logger.info("mission start: %s", self._start_aid)

    def transition_body(self, *items):
        return [it for it in items if isinstance(it, tuple) and len(it) == 2]

    def transition_rule(self, eid: Token, _arrow, nxt_aid: Token, *_nl):
        rule = (str(eid), str(nxt_aid))
        logger.debug("transition_rule: %s -> %s", rule[0], rule[1])
        return rule

    def during_block(self, during_kw, action_id: Token, _nl, rules_list):
        aid = str(action_id)
        self._during.setdefault(aid, {})
        for eid, nxt_aid in rules_list:
            self._during[aid][eid] = nxt_aid
        logger.debug("during_block: %s rules=%s", aid, self._during[aid])

    def mission_block(self, *_children):
        return None

# ===== Attributes / Values =====
    def attr(self, k: Token, _sep, v):
        return (str(k), v)
    
    def value(self, v):
        if isinstance(v, Dict):      # from datum_inline()
            return v
        if isinstance(v, list):      # from array()
            return v
        if isinstance(v, Token):
            t = v.type
            s = str(v)
            if t == "NUMBER":
                return float(s)
            if t == "NAME":
                return s
            if t == "NONE":
                return None
        return v

    def array(self, *items):        
        return [it for it in items if not isinstance(it, Token)]

    def datum_args(self, *items):
        return [it for it in items if not isinstance(it, Token)]

    def datum_inline(self, type_name, *args):
        tname = str(type_name)
        args_list = next((c for c in args if isinstance(c, list)), [])
        return {"__inline__": True, "type": tname, "args": args_list}



    # ===== Top-level =====
    def print_mir(self, mir: MissionIR):
        logger.info("MissionIR:")
        logger.info("  start: %s", mir.start_action_id)

        logger.info("  Data:")
        for did in sorted(mir.data):
            logger.info("    %s", mir.data[did])

        logger.info("  Actions:")
        for aid in sorted(mir.actions):
            logger.info("    %s", mir.actions[aid])

        logger.info("  Events:")
        for eid in sorted(mir.events):
            logger.info("    %s", mir.events[eid])

        logger.info("  Transitions:")
        for state in sorted(mir.transitions):
            evmap = mir.transitions[state]
            for ev in sorted(evmap):
                nxt = evmap[ev]
                logger.info("    %s + %s -> %s", state, ev, nxt)


    def start(self, *children):
        logger.info(
            "transform: building MissionIR (actions=%d, events=%d, data=%d)",
            len(self._actions), len(self._events), len(self._data)
        )

        transitions: Dict[str, Dict[str, str]] = {}
        for aid, evmap in self._during.items():
            am = transitions.setdefault(aid, {})
            am.update(evmap)

        # Ensure every defined action has a default 'done' edge to terminate
        for aid in self._actions.keys():
            logger.info("ensuring action %s has 'done' transition", aid)
            am = transitions.setdefault(aid, {})
            am.setdefault(_DONE_EVENT, _TERMINATE_AID)

        mir = MissionIR(
            actions=self._actions,
            events=self._events,
            data=self._data,
            start_action_id=self._start_aid,
            transitions=transitions
        )

       # Import API so @register_* hooks populate registries
        logger.info("loader: loading SDK registries")
        load_summaries = loader.load_all()
        loader.print_report(load_summaries)
        
        logger.info("resolver: resolving symbol references")
        mir = resolver.resolve_symbols(mir)

        logger.info("validator: validating MissionIR")
        mir = validator.validate_mission_ir(mir)

        logger.info("transform: done (transitions=%d)", len(transitions))
        
        # print the final IR nicely, from data to actions to events
        self.print_mir(mir)
        return mir
