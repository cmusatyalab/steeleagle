# tasks/events/combinators.py
from __future__ import annotations
from typing import List
from pydantic import Field
from ...dsl.compiler.registry import register_event
from ..base import Event


# ========== basic boolean combinators ==========

@register_event
class AnyOf(Event):
    """Fires when ANY child event is true in a poll."""
    events: List[Event] = Field(..., min_items=1)

    async def check(self, context) -> bool:
        for ev in self.events:
            if await ev.check(context):
                return True
        return False


@register_event
class AllOf(Event):
    """Fires when ALL child events are true in the same poll."""
    events: List[Event] = Field(..., min_items=1)

    async def check(self, context) -> bool:
        for ev in self.events:
            if not await ev.check(context):
                return False
        return True


@register_event
class Not(Event):
    """Fires when the child event is false (logical NOT)."""
    event: Event

    async def check(self, context) -> bool:
        return not (await self.event.check(context))


@register_event
class NOfM(Event):
    """Fires when at least N of M child events are true in a poll."""
    n: int = Field(..., gt=0)
    events: List[Event] = Field(..., min_items=1)

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
class Until(Event):
    """
    Fires when `event` becomes true BEFORE `until_event` becomes true.
    If `until_event` fires first, this event will not fire (locks out) until
    both are false again in the same poll (lock resets).
    """
    event: Event
    until_event: Event
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
