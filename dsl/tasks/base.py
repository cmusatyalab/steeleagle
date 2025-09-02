import asyncio
from typing import Any, Dict
from pydantic import BaseModel, ConfigDict

class Executable(BaseModel):
    # Strict validation; allow non-pydantic objects in fields if needed
    model_config = ConfigDict(extra='forbid', arbitrary_types_allowed=True)

    async def execute(self, context):
        raise NotImplementedError

class ExecutableAction(Executable):
    """Marker base for actions (things you execute)."""
    pass

class ExecutableEvent(Executable):
    """Marker base for events (things you wait/observe)."""
    pass


async def event_handler(event: ExecutableEvent, context: Dict[str, Any]) -> None:
    """Waits for event to be true, then returns."""
    while True:
        if await event.check(context):
            return
        await asyncio.sleep(0)