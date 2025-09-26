# compiler/resolver.py
from __future__ import annotations
import logging
from typing import Any, Dict, List, Tuple, get_args, get_origin, Union
from pydantic import BaseModel

from ...dsl.compiler.ir import MissionIR, ActionIR, EventIR, DatumIR
from ...dsl.compiler.registry import get_action, get_event, get_data

logger = logging.getLogger(__name__)


class ResolverException(Exception): ...

def _is_model_type(tp: Any) -> bool:
    try:
        return isinstance(tp, type) and issubclass(tp, BaseModel)
    except Exception:
        return False

def _iter_model_fields(model_cls: type[BaseModel]) -> List[Tuple[str, Any]]:
    out: List[Tuple[str, Any]] = []
    for name, finfo in getattr(model_cls, "model_fields", {}).items():
        out.append((name, finfo.annotation))
    return out

def _instantiate_data_from_ir(did: str, data: Dict[str, DatumIR]) -> BaseModel | None:
    dir = data.get(did)
    if not dir: return None
    cls = get_data(dir.type_name)
    if not cls: 
        logger.warning("instantiate data: unregistered type '%s' (id '%s')", dir.type_name, did)
        raise ResolverException("instantiate data: unregistered type '%s' (id '%s')", dir.type_name, did)
    return cls(**dir.attributes)


def _is_inline_literal(v: Any) -> bool:
    return isinstance(v, dict) and v.get("__inline__") and isinstance(v.get("type"), str)


def _instantiate_inline_data(v, data) -> BaseModel:
    cls = get_data(v["type"])
    if not cls: 
        logger.warning("inline data: unregistered type '%s'", v.get("type"))
        raise ResolverException("inline data: unregistered type '%s'", v.get("type"))

    kwargs = {}
    args = list(v.get("args"))
    fields = _iter_model_fields(cls)
    for idx, (f_name, f_type) in enumerate(fields):
        v = args[idx]
        resolved_v = _resolve_value_for_field(v, f_type, data)
        kwargs[f_name] = resolved_v
    return cls(**kwargs)


def _resolve_value_for_field(
    value: Any,
    field_type: Any,
    data: Dict[str, DatumIR],
) -> Any:
    # Inline first
    if _is_inline_literal(value):
        return _instantiate_inline_data(value, data)

    origin = get_origin(field_type)
    args   = get_args(field_type)

    # Model-typed field: allow string id -> data instance
    if _is_model_type(field_type):
        if isinstance(value, str):
            inst = _instantiate_data_from_ir(value, data)
            return inst if inst is not None else value
        return value

    # list[T]
    if origin in (list, List):
        inner = args[0] if args else Any
        if isinstance(value, list):
            return [_resolve_value_for_field(v, inner, data) for v in value]
        return value
    
    
    # common cases: str, int, float, bool, None
    return value


def resolve_symbols(mir: MissionIR) -> MissionIR:
    """
    Replace string IDs in attributes with *instances* of the referenced models
    (not dicts). Works only for data. Also instantiates inline
    data constructors present in action/event attributes.
    """
    logger.info(
        "resolve_symbols: start (actions=%d, events=%d, data=%d)",
        len(mir.actions), len(mir.events), len(mir.data)
    )

    # 1) DATA first
    for did, dir_ in mir.data.items():
        data_cls = get_data(dir_.type_name)
        if not data_cls:
            logger.warning("resolve_symbols: data '%s' type '%s' not registered", did, dir_.type_name)
            raise ResolverException(f"Data '{did}' type '{dir_.type_name}' not registered")
        resolved = dict(dir_.attributes)
        for fname, ftype in _iter_model_fields(data_cls):
            if fname in resolved:
                resolved[fname] = _resolve_value_for_field(resolved[fname], ftype, mir.data)
        dir_.attributes = resolved

    # 2) ACTIONS
    for aid, air in mir.actions.items():
        action_cls = get_action(air.type_name)
        if not action_cls:
            logger.warning("resolve_symbols: action '%s' type '%s' not registered", aid, air.type_name)
            raise ResolverException(f"Action '{aid}' type '{air.type_name}' not registered")
        resolved = dict(air.attributes)
        for fname, ftype in _iter_model_fields(action_cls):
            if fname in resolved:
                resolved[fname] = _resolve_value_for_field(resolved[fname], ftype, mir.data)
        air.attributes = resolved

    # 3) EVENTS
    for ename, eir in mir.events.items():
        event_cls = get_event(eir.type_name)
        if not event_cls:
            logger.warning("resolve_symbols: event '%s' type '%s' not registered", ename, eir.type_name)
            raise ResolverException(f"Event '{ename}' type '{eir.type_name}' not registered")
        resolved = dict(eir.attributes)
        for fname, ftype in _iter_model_fields(event_cls):
            if fname in resolved:
                resolved[fname] = _resolve_value_for_field(resolved[fname], ftype, mir.data)
        eir.attributes = resolved

    logger.info("resolve_symbols: done")
    return mir
