# compiler/resolver.py
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple, Optional, get_args, get_origin, Union
from pydantic import BaseModel

from dsl.compiler.ir import MissionIR, ActionIR, EventIR, DatumIR
from dsl.compiler.registry import get_action, get_event, get_data

logger = logging.getLogger(__name__)


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


def _instantiate_action_from_ir(aid: str, actions: Dict[str, ActionIR]) -> BaseModel | None:
    air = actions.get(aid)
    if not air:
        return None
    cls = get_action(air.type_name)
    if not cls:
        logger.warning("instantiate action: unregistered type '%s' (id '%s')", air.type_name, aid)
        return None
    return cls(**air.attributes)


def _instantiate_event_from_ir(eid: str, events: Dict[str, EventIR]) -> BaseModel | None:
    eir = events.get(eid)
    if not eir:
        return None
    cls = get_event(eir.type_name)
    if not cls:
        logger.warning("instantiate event: unregistered type '%s' (id '%s')", eir.type_name, eid)
        return None
    return cls(**eir.attributes)


def _instantiate_data_from_ir(did: str, data: Dict[str, DatumIR]) -> BaseModel | None:
    dir_ = data.get(did)
    if not dir_:
        return None
    cls = get_data(dir_.type_name)
    if not cls:
        logger.warning("instantiate data: unregistered type '%s' (id '%s')", dir_.type_name, did)
        return None
    return cls(**dir_.attributes)


def _maybe_instantiate_inline_data(v):
    if not (isinstance(v, dict) and v.get("__inline__") and "type" in v):
        return v

    cls = get_data(v["type"])
    if not cls:
        logger.warning("inline data: unregistered type '%s'", v["type"])
        return v

    try:
        kwargs = dict(v.get("kwargs") or {})
        args = list(v.get("args") or [])

        if args:
            field_names = list(cls.model_fields.keys())
            ai = 0
            for fn in field_names:
                if fn in kwargs:
                    continue
                if ai < len(args):
                    kwargs[fn] = args[ai]
                    ai += 1
                else:
                    break

        return cls(**kwargs)
    except Exception as e:
        logger.error("inline data: failed to instantiate %s: %s", v["type"], e)
        return v


def _resolve_value_for_field(
    value: Any,
    field_type: Any,
    actions: Dict[str, ActionIR],
    events: Dict[str, EventIR],
    data: Dict[str, DatumIR],
) -> Any:
    """
    Convert:
      - inline data literals -> BaseModel via get_data
      - string IDs          -> BaseModel via get_data/get_event/get_action
    Handles nested List/Tuple/Optional types.
    """
    # First: materialize any inline data literal
    value = _maybe_instantiate_inline_data(value)

    origin = get_origin(field_type)
    args   = get_args(field_type)

    # Field expects a Pydantic model
    if _is_model_type(field_type):
        if isinstance(value, str):
            inst = (
                _instantiate_data_from_ir(value, data)
                or _instantiate_event_from_ir(value, events)
                or _instantiate_action_from_ir(value, actions)
            )
            return inst if inst is not None else value
        # Already a BaseModel or nested dict/list: leave or recurse where needed
        return value

    # List/Tuple fields
    if origin in (list, List, tuple, Tuple):
        inner = args[0] if args else Any
        if isinstance(value, (list, tuple)):
            out_list = []
            for v in value:
                v = _maybe_instantiate_inline_data(v)
                if _is_model_type(inner) and isinstance(v, str):
                    inst = (
                        _instantiate_data_from_ir(v, data)
                        or _instantiate_event_from_ir(v, events)
                        or _instantiate_action_from_ir(v, actions)
                    )
                    out_list.append(inst if inst is not None else v)
                else:
                    out_list.append(_resolve_value_for_field(v, inner, actions, events, data))
            return out_list
        return value

    # Optional / Union
    if origin is Union and args:
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _resolve_value_for_field(value, non_none[0], actions, events, data)

    return value


def resolve_symbols(mir: MissionIR) -> MissionIR:
    """
    Replace string IDs in attributes with *instances* of the referenced models
    (not dicts). Works for actions, events, and data. Also instantiates inline
    data constructors present in action/event attributes.
    """
    logger.info(
        "resolve_symbols: start (actions=%d, events=%d, data=%d)",
        len(mir.actions), len(mir.events), len(mir.data)
    )

    # actions
    for aid, air in mir.actions.items():
        action_cls = get_action(air.type_name)
        if not action_cls:
            logger.warning("resolve_symbols: action '%s' type '%s' not registered", aid, air.type_name)
            continue
        resolved = dict(air.attributes)
        for fname, ftype in _iter_model_fields(action_cls):
            if fname in resolved:
                resolved[fname] = _resolve_value_for_field(
                    resolved[fname], ftype, mir.actions, mir.events, mir.data
                )
        air.attributes = resolved

    # events
    for ename, eir in mir.events.items():
        event_cls = get_event(eir.type_name)
        if not event_cls:
            logger.warning("resolve_symbols: event '%s' type '%s' not registered", ename, eir.type_name)
            continue
        resolved = dict(eir.attributes)
        for fname, ftype in _iter_model_fields(event_cls):
            if fname in resolved:
                resolved[fname] = _resolve_value_for_field(
                    resolved[fname], ftype, mir.actions, mir.events, mir.data
                )
        eir.attributes = resolved

    # data (allow data objects to embed other data as fields, if schema uses them)
    for did, dir_ in mir.data.items():
        data_cls = get_data(dir_.type_name)
        if not data_cls:
            logger.warning("resolve_symbols: data '%s' type '%s' not registered", did, dir_.type_name)
            continue
        resolved = dict(dir_.attributes)
        for fname, ftype in _iter_model_fields(data_cls):
            if fname in resolved:
                resolved[fname] = _resolve_value_for_field(
                    resolved[fname], ftype, mir.actions, mir.events, mir.data
                )
        dir_.attributes = resolved

    logger.info("resolve_symbols: done")
    return mir
