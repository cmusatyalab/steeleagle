"""DSL text -> FSM graph helpers shared by /api/parse_dsl and /api/chat."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import steeleagle_sdk
from lark import Lark, Token, Transformer, UnexpectedInput, v_args

_GRAMMAR_PATH = Path(steeleagle_sdk.__path__[0]) / "dsl" / "grammar" / "dronedsl.lark"
_dsl_parser: Lark | None = None


def init_dsl_parser() -> Lark | None:
    """Initialize (or re-initialize) the shared Lark parser. Returns parser or None."""
    global _dsl_parser
    try:
        _dsl_parser = Lark.open(
            str(_GRAMMAR_PATH), parser="earley", start="start", ambiguity="resolve"
        )
        return _dsl_parser
    except Exception:
        _dsl_parser = None
        raise


def get_dsl_parser() -> Lark | None:
    return _dsl_parser


def grammar_path() -> Path:
    return _GRAMMAR_PATH


@v_args(inline=True)
class RawDslExtractor(Transformer):
    """
    Lark transformer that extracts the structural skeleton of a DSL file as plain
    Python dicts without resolving types or running the validator.
    Data-section references are expanded to their attribute dicts.
    """

    def __init__(self):
        super().__init__()
        self._data: dict[str, dict] = {}
        self._actions: list[dict] = []
        self._events: list[dict] = []
        self._start_id: str | None = None
        self._during: dict[str, dict[str, str]] = {}

    def _pairs_to_dict(self, items) -> dict:
        if items is None:
            return {}
        return {k: v for k, v in items if isinstance(k, str)}

    def _resolve_val(self, v: Any) -> Any:
        if isinstance(v, str) and v in self._data:
            return dict(self._data[v]["attrs"])
        return v

    def _resolve_attrs(self, attrs: dict) -> dict:
        return {k: self._resolve_val(v) for k, v in attrs.items()}

    def datum_body(self, *items):
        return [it for it in items if isinstance(it, tuple)]

    def datum_decl(self, type_name: Token, datum_id: Token, attrs=None):
        did = str(datum_id)
        self._data[did] = {
            "type_name": str(type_name),
            "attrs": self._pairs_to_dict(attrs or []),
        }

    def action_body(self, *items):
        return [it for it in items if isinstance(it, tuple)]

    def action_decl(self, type_name: Token, action_id: Token, attrs=None):
        self._actions.append(
            {
                "type_name": str(type_name),
                "instance_id": str(action_id),
                "params": self._resolve_attrs(self._pairs_to_dict(attrs or [])),
            }
        )

    def event_body(self, *items):
        return [it for it in items if isinstance(it, tuple)]

    def event_decl(self, type_name: Token, event_id: Token, attrs=None):
        self._events.append(
            {
                "type_name": str(type_name),
                "instance_id": str(event_id),
                "params": self._resolve_attrs(self._pairs_to_dict(attrs or [])),
            }
        )

    def mission_start(self, _kw: Token, action_id: Token, *_rest):
        self._start_id = str(action_id)

    def transition_rule(self, eid: Token, _arrow: Token, nxt_aid: Token, *_rest):
        return (str(eid), str(nxt_aid))

    def transition_body(self, *items):
        return [it for it in items if isinstance(it, tuple)]

    def during_block(self, _kw: Token, action_id: Token, *rest):
        aid = str(action_id)
        self._during.setdefault(aid, {})
        rules_list = next((r for r in rest if isinstance(r, list)), [])
        for eid, nxt in rules_list:
            self._during[aid][eid] = nxt

    def mission_block(self, *_):
        return None

    def attr(self, k: Token, _sep, v):
        return (str(k), v)

    def value(self, v):
        if isinstance(v, dict | list):
            return v
        if isinstance(v, Token):
            if v.type == "NUMBER":
                return float(str(v))
            if v.type == "NAME":
                return str(v)
            if v.type == "NONE":
                return None
        return v

    def array(self, *items):
        return [it for it in items if not isinstance(it, Token)]

    def datum_args(self, *items):
        return [it for it in items if not isinstance(it, Token)]

    def datum_inline(self, type_name: Token, *args):
        args_list = next((c for c in args if isinstance(c, list)), [])
        return {"__inline__": True, "type": str(type_name), "args": args_list}

    def start(self, *_children):
        edges = []
        for source, evmap in self._during.items():
            for eid, target in evmap.items():
                if target != "terminate":
                    edges.append({"source": source, "event_id": eid, "target": target})
        return {
            "nodes": self._actions,
            "events": self._events,
            "edges": edges,
            "start_id": self._start_id,
        }


def parse_dsl_to_graph(dsl: str) -> dict[str, Any]:
    """Parse DSL text into {nodes, events, edges, start_id}. Raises on parse failure."""
    parser = get_dsl_parser()
    if parser is None:
        raise RuntimeError("DSL parser not initialized")
    tree = parser.parse(dsl)
    return RawDslExtractor().transform(tree)


__all__ = [
    "RawDslExtractor",
    "UnexpectedInput",
    "get_dsl_parser",
    "grammar_path",
    "init_dsl_parser",
    "parse_dsl_to_graph",
]
