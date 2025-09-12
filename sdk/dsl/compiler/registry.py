from typing import Type, Dict, Optional
from ...api.base import Action, Event, Datatype
import logging

logger = logging.getLogger(__name__)

_ACTIONS: Dict[str, Action] = {}
_EVENTS: Dict[str, Event] = {}
_DATA: Dict[str, Datatype] = {}

def _norm(name: str) -> str:
    return (name or "").strip().lower()

def register_action(cls: Action) -> Action:
    key = _norm(cls.__name__)
    prev = _ACTIONS.get(key)
    _ACTIONS[key] = cls
    if prev and prev is not cls:
        logger.warning("Overwriting action '%s'", key)
    else:
        logger.info("Registered action '%s'", key)
    return cls

def register_event(cls: Event) -> Event:
    key = _norm(cls.__name__)
    prev = _EVENTS.get(key)
    _EVENTS[key] = cls
    if prev and prev is not cls:
        logger.warning("Overwriting event '%s'", key)
    else:
        logger.info("Registered event '%s'", key)
    return cls

def register_data(cls: Datatype) -> Datatype:
    key = _norm(cls.__name__)
    prev = _DATA.get(key)
    _DATA[key] = cls
    if prev and prev is not cls:
        logger.warning("Overwriting message '%s'", key)
    else:
        logger.info("Registered message '%s'", key)
    return cls

def get_action(name: str) -> Optional[Action]:
    return _ACTIONS.get(_norm(name))

def get_event(name: str) -> Optional[Event]:
    return _EVENTS.get(_norm(name))

def get_data(name: str) -> Optional[Datatype]:
    return _DATA.get(_norm(name))
