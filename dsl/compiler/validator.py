# compiler/validator.py
from __future__ import annotations

from typing import Any, Dict, Tuple
from pydantic import BaseModel, ValidationError

from compiler.registry import get_action, get_event
from compiler.ir import MissionIR


class DSLValidationError(ValueError):
    """Compact error used at the DSL surface."""


def _instantiate(cls: type[BaseModel], attrs: Dict[str, Any]) -> BaseModel:
    try:
        return cls(**attrs)
    except ValidationError as e:
        msgs = "; ".join(err["msg"] for err in e.errors())
        raise DSLValidationError(msgs) from e
    except Exception as e:
        raise DSLValidationError(str(e)) from e


def validate_action(type_name: str, attrs: Dict[str, Any]) -> Tuple[type[BaseModel], Dict[str, Any]]:
    cls = get_action(type_name)
    if cls is None:
        raise DSLValidationError(f"Unregistered action type: {type_name}")
    model = _instantiate(cls, attrs)
    return cls, model.model_dump()


def validate_event(type_name: str, attrs: Dict[str, Any]) -> Tuple[type[BaseModel], Dict[str, Any]]:
    cls = get_event(type_name)
    if cls is None:
        raise DSLValidationError(f"Unregistered event type: {type_name}")
    model = _instantiate(cls, attrs)
    return cls, model.model_dump()


def validate_mission_ir(mir: MissionIR) -> MissionIR:
    """
    Validate and normalize every action and event in the MissionIR.
    Returns the same object with attributes replaced by normalized dumps.
    """
    # Actions
    for aid, air in mir.actions.items():
        try:
            _, normalized = validate_action(air.type_name, air.attributes)
            air.attributes = normalized
        except DSLValidationError as e:
            raise ValueError(
                f"Action '{aid}' of type '{air.type_name}' failed validation: {e}"
            ) from e

    # Events
    for ename, eir in mir.events.items():
        try:
            _, normalized = validate_event(eir.type_name, eir.attributes)
            eir.attributes = normalized
        except DSLValidationError as e:
            raise ValueError(
                f"Event '{ename}' of type '{eir.type_name}' failed validation: {e}"
            ) from e

    return mir