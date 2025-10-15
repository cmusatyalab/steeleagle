# compiler/resolver.py
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple, Union, Annotated, get_args, get_origin, get_type_hints
from pydantic import BaseModel

from ...dsl.compiler.ir import MissionIR, ActionIR, EventIR, DatumIR
from ...dsl.compiler.registry import get_action, get_event, get_data

logger = logging.getLogger(__name__)


class ResolverException(Exception):
    ...


# ---------- Type utilities ----------

def _unwrap_type(tp: Any) -> Any:
    origin = get_origin(tp)

    if origin is Annotated:
        # Annotated[T, ...] -> T
        base = get_args(tp)[0]
        return _unwrap_type(base)

    if origin is Union:
        # Optional[T] -> Union[T, NoneType]
        non_none = [a for a in get_args(tp) if a is not type(None)]
        if len(non_none) == 1:
            return _unwrap_type(non_none[0])
        # Multiple real choices: give up on unwrapping
        return tp

    return tp


def _is_model_type(tp: Any) -> bool:
    core = _unwrap_type(tp)
    try:
        return isinstance(core, type) and issubclass(core, BaseModel)
    except Exception:
        return False


def _iter_model_fields(model_cls: type[BaseModel]) -> List[Tuple[str, Any]]:
    out: List[Tuple[str, Any]] = []
    hints = get_type_hints(model_cls, include_extras=True)
    for name, finfo in getattr(model_cls, "model_fields", {}).items():
        out.append((name, hints.get(name, finfo.annotation)))
    return out


# ---------- Data instantiation helpers ----------

def _instantiate_data_from_ir(did: str, data: Dict[str, DatumIR]) -> BaseModel | None:
    dir_ = data.get(did)
    if not dir_:
        return None

    cls = get_data(dir_.type_name)
    if not cls:
        logger.warning("instantiate data: unregistered type '%s' (id '%s')", dir_.type_name, did)
        raise ResolverException(
            f"instantiate data: unregistered type '{dir_.type_name}' (id '{did}')"
        )

    return cls(**dir_.attributes)


def _is_inline_literal(v: Any) -> bool:
    return isinstance(v, dict) and v.get("__inline__") and isinstance(v.get("type"), str)


def _instantiate_inline_data(v: Dict[str, Any], data: Dict[str, DatumIR]) -> BaseModel:
    cls = get_data(v["type"])
    if not cls:
        logger.warning("inline data: unregistered type '%s'", v.get("type"))
        raise ResolverException(f"inline data: unregistered type '{v.get('type')}'")

    kwargs: Dict[str, Any] = {}
    args = list(v.get("args", []))
    fields = _iter_model_fields(cls)

    for idx, (f_name, f_type) in enumerate(fields):
        if idx >= len(args):
            # Leave missing args to Pydantic defaults/validation
            continue
        raw_val = args[idx]
        resolved_val = _resolve_value_for_field(raw_val, f_type, data)
        kwargs[f_name] = resolved_val

    return cls(**kwargs)


# ---------- Core resolver ----------

def _resolve_value_for_field(
    value: Any,
    field_type: Any,
    data: Dict[str, DatumIR],
) -> Any:
    # Explicit None: keep it
    if value is None:
        return None

    # Inline constructor first
    if _is_inline_literal(value):
        return _instantiate_inline_data(value, data)

    core = _unwrap_type(field_type)
    origin = get_origin(core)
    args = get_args(core)

    # Model field (e.g., Velocity, Position)
    if _is_model_type(core):
        if isinstance(value, str):
            # Convert datum id -> model instance
            inst = _instantiate_data_from_ir(value, data)
            return inst if inst is not None else value
        # If it's already a dict or model, let Pydantic do the rest
        return value

    # Lists (also handles Optional[List[T]], Annotated[List[T], ...])
    if origin in (list, List):
        inner = args[0] if args else Any
        if isinstance(value, list):
            return [_resolve_value_for_field(v, inner, data) for v in value]
        return value

    # Primitives / enums / passthrough
    return value


def resolve_symbols(mir: MissionIR) -> MissionIR:
    """
    Replace string IDs in attributes with *instances* of the referenced data models
    when the target field is a model type. Also instantiate inline data constructors
    in action/event attributes. For Data objects, resolve nested references inside
    their attribute dicts so that later instantiation sees already-resolved values.
    """
    logger.info(
        "resolve_symbols: start (actions=%d, events=%d, data=%d)",
        len(mir.actions), len(mir.events), len(mir.data)
    )

    # 1) DATA — resolve references inside DatumIR.attributes (but keep as dict)
    for did, dir_ in mir.data.items():
        data_cls = get_data(dir_.type_name)
        if not data_cls:
            logger.warning("resolve_symbols: data '%s' type '%s' not registered", did, dir_.type_name)
            raise ResolverException(f"Data '{did}' type '{dir_.type_name}' not registered")
        resolved_attrs = dict(dir_.attributes)
        for fname, ftype in _iter_model_fields(data_cls):
            if fname in resolved_attrs:
                resolved_attrs[fname] = _resolve_value_for_field(resolved_attrs[fname], ftype, mir.data)
        dir_.attributes = resolved_attrs

    # 2) ACTIONS — resolve to instances/inline models where appropriate
    for aid, air in mir.actions.items():
        action_cls = get_action(air.type_name)
        if not action_cls:
            logger.warning("resolve_symbols: action '%s' type '%s' not registered", aid, air.type_name)
            raise ResolverException(f"Action '{aid}' type '{air.type_name}' not registered")
        resolved_attrs = dict(air.attributes)
        for fname, ftype in _iter_model_fields(action_cls):
            if fname in resolved_attrs:
                resolved_attrs[fname] = _resolve_value_for_field(resolved_attrs[fname], ftype, mir.data)
        air.attributes = resolved_attrs

    # 3) EVENTS — same treatment as actions
    for ename, eir in mir.events.items():
        event_cls = get_event(eir.type_name)
        if not event_cls:
            logger.warning("resolve_symbols: event '%s' type '%s' not registered", ename, eir.type_name)
            raise ResolverException(f"Event '{ename}' type '{eir.type_name}' not registered")
        resolved_attrs = dict(eir.attributes)
        for fname, ftype in _iter_model_fields(event_cls):
            if fname in resolved_attrs:
                resolved_attrs[fname] = _resolve_value_for_field(resolved_attrs[fname], ftype, mir.data)
        eir.attributes = resolved_attrs

    logger.info("resolve_symbols: done")
    return mir
