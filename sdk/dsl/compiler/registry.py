from typing import Type, Dict, Optional
from pydantic import BaseModel
import logging

# Module logger
logger = logging.getLogger(__name__)

ActionCls = Type[BaseModel]
EventCls  = Type[BaseModel]

_ACTIONS: Dict[str, ActionCls] = {}
_EVENTS: Dict[str, EventCls] = {}

def _norm(name: str) -> str:
    return (name or "").strip().lower()

def register_action(cls: ActionCls) -> ActionCls:
    key = _norm(cls.__name__)
    prev = _ACTIONS.get(key)
    _ACTIONS[key] = cls
    if prev is not None and prev is not cls:
        logger.warning("Overwriting action for key '%s': %r -> %r", key, prev, cls)
    else:
        logger.info("Registered action '%s' as key '%s'", cls.__name__, key)
    return cls

def register_event(cls: EventCls) -> EventCls:
    key = _norm(cls.__name__)
    prev = _EVENTS.get(key)
    _EVENTS[key] = cls
    if prev is not None and prev is not cls:
        logger.warning("Overwriting event for key '%s': %r -> %r", key, prev, cls)
    else:
        logger.info("Registered event '%s' as key '%s'", cls.__name__, key)
    return cls

def get_action(name: str) -> Optional[ActionCls]:
    key = _norm(name)
    cls = _ACTIONS.get(key)
    if cls is None:
        logger.debug("Action lookup miss for '%s' (key '%s')", name, key)
    else:
        logger.debug("Action lookup hit for '%s' -> %r", name, cls)
    return cls

def get_event(name: str) -> Optional[EventCls]:
    key = _norm(name)
    cls = _EVENTS.get(key)
    if cls is None:
        logger.debug("Event lookup miss for '%s' (key '%s')", name, key)
    else:
        logger.debug("Event lookup hit for '%s' -> %r", name, cls)
    return cls
