from __future__ import annotations

import asyncio
import contextlib
import logging
from enum import Enum
from typing import Optional, Dict, List, Tuple, Any

from ...dsl.compiler.ir import MissionIR
from ...dsl.compiler.registry import get_action, get_event

logger = logging.getLogger(__name__)

_DONE_EVENT = "done"
_TERMINATE = "terminate"


class RacerType(str, Enum):
    ACTION = "action"
    EVENT  = "event"
    ERROR  = "error"


class MissionFSM:
    def __init__(self, mission: MissionIR):
        self.mission = mission
        self.transition: Dict[str, Dict[str, str]] = mission.transitions
        self.start_action_id: str = mission.start_action_id
        
    async def run(self):
        state = self.start_action_id
        while state != _TERMINATE:
            state = await self.run_state(state)
        logger.info("[FSM] Mission complete")

    async def run_state(self, curr_action_id: str) -> str:
        action_ir = self.mission.actions[curr_action_id]
        action_cls = get_action(action_ir.type_name)
        action = action_cls(**action_ir.attributes)

        logger.info("[FSM] action %s: %s", curr_action_id, action_ir.type_name)
        event_ids = [e for e in self._gather_events(curr_action_id) if e != _DONE_EVENT]
        logger.info("[FSM] events: %s", event_ids)

        q: asyncio.Queue[Tuple[RacerType, Any]] = asyncio.Queue(maxsize=1)
        winner: Tuple[RacerType, Any]

        async with asyncio.TaskGroup() as tg:
            members: List[asyncio.Task] = []

            # Action
            members.append(
                tg.create_task(self._race(action, RacerType.ACTION, curr_action_id, q),
                               name=f"action:{curr_action_id}")
            )

            # Events
            for ev_id in event_ids:
                ev_ir = self.mission.events[ev_id]
                ev_cls = get_event(ev_ir.type_name)
                ev = ev_cls(**ev_ir.attributes)
                members.append(
                    tg.create_task(self._race(ev, RacerType.EVENT, ev_id, q),
                                   name=f"event:{ev_id}")
                )

            # First finisher places a result into q
            winner = await q.get()

            # Cancel everyone else
            for t in members:
                t.cancel()

        kind, payload = winner
        if kind is RacerType.ERROR:
            logger.exception("[FSM] Winner failed in state %s", curr_action_id, exc_info=payload)
            return _TERMINATE

        if kind is RacerType.ACTION:
            logger.info("[FSM] action %s completed", curr_action_id)
            return self._next_state(curr_action_id, _DONE_EVENT)

        if kind is RacerType.EVENT:
            logger.info("[FSM] event %s triggered", payload)
            return self._next_state(curr_action_id, str(payload))

        logger.error("[FSM] Unknown winner kind: %s", kind)
        return _TERMINATE

    async def _race(
        self,
        racer: Any,                         # has .execute() for ACTION, .check() for EVENT
        racer_type: RacerType,
        racer_id: str,
        q: asyncio.Queue[Tuple[RacerType, Any]],
    ) -> None:
        try:
            if racer_type is RacerType.ACTION:
                await racer.execute()
            else:  # RacerType.EVENT
                await racer.check()

            try:
                q.put_nowait((racer_type, racer_id))
            except asyncio.QueueFull:
                pass

        except Exception as e:
            try:
                q.put_nowait((RacerType.ERROR, e))
            except asyncio.QueueFull:
                pass
            raise

    def _gather_events(self, curr_action_id: str) -> List[str]:
        return list(self.transition.get(curr_action_id, {}).keys())

    def _next_state(self, curr_action_id: str, ev_id: str) -> str:
        nxt = self.transition.get(curr_action_id, {}).get(ev_id)
        if nxt is None:
            logger.error("[FSM] No transition for (%s, %s)", curr_action_id, ev_id)
            return _TERMINATE
        return nxt
