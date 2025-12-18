from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionIR:
    type_name: str
    action_id: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class EventIR:
    type_name: str
    event_id: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class DatumIR:
    type_name: str
    datum_id: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class MissionIR:
    actions: dict[str, ActionIR]
    events: dict[str, EventIR]
    data: dict[str, DatumIR]
    start_action_id: str
    # transitions: (action, event) -> next_action
    transitions: dict[str, dict[str, str]]
