# compiler/symbols.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional, get_args, get_origin, Union
from pydantic import BaseModel

from compiler.ir import MissionIR, ActionIR, EventIR
from compiler.registry import get_action, get_event


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
    """Given an action id, build its concrete Pydantic instance from registry."""
    air = actions.get(aid)
    if not air:
        return None
    cls = get_action(air.type_name)
    if not cls:
        return None
    # instantiate (validates + normalizes nested scalars immediately)
    return cls(**air.attributes)


def _instantiate_event_from_ir(eid: str, events: Dict[str, EventIR]) -> BaseModel | None:
    """Given an event id, build its concrete Pydantic instance from registry."""
    eir = events.get(eid)
    if not eir:
        return None
    cls = get_event(eir.type_name)
    if not cls:
        return None
    return cls(**eir.attributes)


def _resolve_value_for_field(
    value: Any,
    field_type: Any,
    actions: Dict[str, ActionIR],
    events: Dict[str, EventIR],
) -> Any:
    """
    Convert string IDs to concrete BaseModel *instances* using the registry,
    based on the field type. Supports nested List/Tuple/Optional.
    """
    origin = get_origin(field_type)
    args   = get_args(field_type)

    # Single nested model field
    if _is_model_type(field_type):
        # Try event/action id -> instance
        if isinstance(value, str):
            inst = _instantiate_event_from_ir(value, events) or _instantiate_action_from_ir(value, actions)
            return inst if inst is not None else value
        # Already a BaseModel or dict: leave as-is (dicts may be inline specs)
        return value

    # List/Tuple fields
    if origin in (list, List, tuple, Tuple):
        inner = args[0] if args else Any
        if isinstance(value, (list, tuple)):
            out_list = []
            for v in value:
                if _is_model_type(inner) and isinstance(v, str):
                    inst = _instantiate_event_from_ir(v, events) or _instantiate_action_from_ir(v, actions)
                    out_list.append(inst if inst is not None else v)
                else:
                    out_list.append(_resolve_value_for_field(v, inner, actions, events))
            return out_list
        return value

    # Optional / Union
    if origin is Union and args:
        # Prefer first non-None arg
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _resolve_value_for_field(value, non_none[0], actions, events)

    return value


def resolve_symbols(mir: MissionIR) -> MissionIR:
    """
    Replace string IDs in attributes with *instances* of the referenced models
    (not dicts). This enables polymorphic fields like List[ExecutableEvent].
    """
    # Resolve action fields
    for aid, air in mir.actions.items():
        action_cls = get_action(air.type_name)
        if not action_cls:
            continue
        resolved = dict(air.attributes)
        for fname, ftype in _iter_model_fields(action_cls):
            if fname in resolved:
                resolved[fname] = _resolve_value_for_field(
                    resolved[fname], ftype, mir.actions, mir.events
                )
        air.attributes = resolved

    # Resolve event fields
    for ename, eir in mir.events.items():
        event_cls = get_event(eir.type_name)
        if not event_cls:
            continue
        resolved = dict(eir.attributes)
        for fname, ftype in _iter_model_fields(event_cls):
            if fname in resolved:
                resolved[fname] = _resolve_value_for_field(
                    resolved[fname], ftype, mir.actions, mir.events
                )
        eir.attributes = resolved

    return mir
