# tasks/events/combinators.py
from __future__ import annotations

import asyncio
from typing import List, Optional
from pydantic import Field, ConfigDict
from compiler.registry import register_event
from tasks.base import ExecutableEvent


# ========== basic boolean combinators ==========

@register_event
class AnyOf(ExecutableEvent):
    """Fires when ANY child event is true in a poll."""
    events: List[ExecutableEvent] = Field(..., min_items=1)

    async def check(self, context) -> bool:
        for ev in self.events:
            if await ev.check(context):
                return True
        return False


@register_event
class AllOf(ExecutableEvent):
    """Fires when ALL child events are true in the same poll."""
    events: List[ExecutableEvent] = Field(..., min_items=1)

    async def check(self, context) -> bool:
        for ev in self.events:
            if not await ev.check(context):
                return False
        return True


@register_event
class Not(ExecutableEvent):
    """Fires when the child event is false (logical NOT)."""
    event: ExecutableEvent

    async def check(self, context) -> bool:
        return not (await self.event.check(context))


@register_event
class NOfM(ExecutableEvent):
    """Fires when at least N of M child events are true in a poll."""
    n: int = Field(..., gt=0)
    events: List[ExecutableEvent] = Field(..., min_items=1)

    async def check(self, context) -> bool:
        count = 0
        for ev in self.events:
            if await ev.check(context):
                count += 1
                if count >= self.n:
                    return True
        return False


# ========== time/state aware combinators ==========

@register_event
class Until(ExecutableEvent):
    """
    Fires when `event` becomes true BEFORE `until_event` becomes true.
    If `until_event` fires first, this event will not fire (locks out) until
    both are false again in the same poll (lock resets).
    """
    event: ExecutableEvent
    until_event: ExecutableEvent
    _locked_out: bool = False

    async def check(self, context) -> bool:
        until_hit = await self.until_event.check(context)
        if until_hit:
            self._locked_out = True
            return False
        if self._locked_out:
            # reset lock when both are false in the same poll
            ev_now = await self.event.check(context)
            if not ev_now and not until_hit:
                self._locked_out = False
            return False
        return await self.event.check(context)
