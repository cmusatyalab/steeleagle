from typing import Type, Dict, Optional
from pydantic import BaseModel

ActionCls = Type[BaseModel]
EventCls  = Type[BaseModel]

_ACTIONS: Dict[str, ActionCls] = {}
_EVENTS: Dict[str, EventCls] = {}

def _norm(name: str) -> str:
    return name.strip().lower()

def register_action(cls: ActionCls) -> ActionCls:
    name = cls.__name__
    _ACTIONS[_norm(name)] = cls
    return cls

def register_event(cls: EventCls) -> EventCls:
    name = cls.__name__
    _EVENTS[_norm(name)] = cls
    return cls

def get_action(name: str) -> Optional[ActionCls]:
    return _ACTIONS.get(_norm(name))

def get_event(name: str) -> Optional[EventCls]:
    return _EVENTS.get(_norm(name))
