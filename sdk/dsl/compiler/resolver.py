# compiler/symbols.py
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple, Optional, get_args, get_origin, Union
from pydantic import BaseModel

from dsl.compiler.ir import MissionIR, ActionIR, EventIR
from dsl.compiler.registry import get_action, get_event

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
    """Given an action id, build its concrete Pydantic instance from registry."""
    air = actions.get(aid)
    if not air:
        logger.debug("instantiate action: unknown action id '%s'", aid)
        return None
    cls = get_action(air.type_name)
    if not cls:
        logger.warning("instantiate action: unregistered action type '%s' (id '%s')",
                       air.type_name, aid)
        return None
    return cls(**air.attributes)


def _instantiate_event_from_ir(eid: str, events: Dict[str, EventIR]) -> BaseModel | None:
    """Given an event id, build its concrete Pydantic instance from registry."""
    eir = events.get(eid)
    if not eir:
        logger.debug("instantiate event: unknown event id '%s'", eid)
        return None
    cls = get_event(eir.type_name)
    if not cls:
        logger.warning("instantiate event: unregistered event type '%s' (id '%s')",
                       eir.type_name, eid)
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
        if isinstance(value, str):
            inst = _instantiate_event_from_ir(value, events) or _instantiate_action_from_ir(value, actions)
            if inst is None:
                logger.debug("symbol resolve: left string ref '%s' as-is (no matching action/event)", value)
            return inst if inst is not None else value
        return value

    # List/Tuple fields
    if origin in (list, List, tuple, Tuple):
        inner = args[0] if args else Any
        if isinstance(value, (list, tuple)):
            out_list = []
            for v in value:
                if _is_model_type(inner) and isinstance(v, str):
                    inst = _instantiate_event_from_ir(v, events) or _instantiate_action_from_ir(v, actions)
                    if inst is None:
                        logger.debug("symbol resolve: list item '%s' left as-is (no match)", v)
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
    logger.info("resolve_symbols: start (actions=%d, events=%d)", len(mir.actions), len(mir.events))

    missing_action_types = 0
    missing_event_types = 0
    fields_resolved = 0

    # Resolve action fields
    for aid, air in mir.actions.items():
        action_cls = get_action(air.type_name)
        if not action_cls:
            missing_action_types += 1
            logger.warning("resolve_symbols: action '%s' type '%s' not registered", aid, air.type_name)
            continue
        resolved = dict(air.attributes)
        for fname, ftype in _iter_model_fields(action_cls):
            if fname in resolved:
                before = resolved[fname]
                after = _resolve_value_for_field(before, ftype, mir.actions, mir.events)
                if after is not before:
                    fields_resolved += 1
                resolved[fname] = after
        air.attributes = resolved

    # Resolve event fields
    for ename, eir in mir.events.items():
        event_cls = get_event(eir.type_name)
        if not event_cls:
            missing_event_types += 1
            logger.warning("resolve_symbols: event '%s' type '%s' not registered", ename, eir.type_name)
            continue
        resolved = dict(eir.attributes)
        for fname, ftype in _iter_model_fields(event_cls):
            if fname in resolved:
                before = resolved[fname]
                after = _resolve_value_for_field(before, ftype, mir.actions, mir.events)
                if after is not before:
                    fields_resolved += 1
                resolved[fname] = after
        eir.attributes = resolved

    logger.info(
        "resolve_symbols: done (fields_resolved=%d, missing_action_types=%d, missing_event_types=%d)",
        fields_resolved, missing_action_types, missing_event_types
    )
    return mir
