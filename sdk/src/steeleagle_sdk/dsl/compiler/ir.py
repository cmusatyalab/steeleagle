from dataclasses import dataclass, field
from typing import Dict, Tuple, Any

@dataclass
class ActionIR:
    type_name: str
    action_id: str
    attributes: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EventIR:
    type_name: str
    event_id: str
    attributes: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DatumIR:
    type_name: str
    datum_id: str
    attributes: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MissionIR:
    actions: Dict[str, ActionIR]
    events: Dict[str, EventIR]
    data: Dict[str, DatumIR]
    start_action_id: str
    # transitions: (action, event) -> next_action
    transitions: Dict[str, Dict[str, str]]
