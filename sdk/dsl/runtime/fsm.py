from __future__ import annotations
import asyncio
from ...dsl.compiler.ir import MissionIR
from ...dsl.compiler.registry import get_action, get_event
import logging


logger = logging.getLogger(__name__)

# need to refine these
_DONE_EVENT = "done"
_TERMINATE = "terminate"

class MissionFSM:
    def __init__(self, mission: MissionIR):
        self.mission = mission
        logger.info(f"[FSM] Initialized with mission: {mission}")
        self.transition = mission.transitions
        self.start_action_id = mission.start_action_id
        self.stop_requested = False

    async def run(self):
        # get the start action
        start_action_id = self.start_action_id
        state = start_action_id
        while (state != _TERMINATE and not self.stop_requested):
            result_event = await self.run_state(state)
            next_state = self.transition[state][result_event]
            state = next_state
            
    async def stop(self):
        self.stop_requested = True

    async def run_state(self, curr_action_id):
        action_ir = self.mission.actions[curr_action_id]
        action_cls = get_action(action_ir.type_name)
        action = action_cls(**action_ir.attributes)

        logger.info(f"[FSM] Entering state={curr_action_id}")

        # --- Create async task for the action itself ---
        action_task = asyncio.create_task(action.execute())
        logger.info(f"[FSM] Action task created: {action_task}")
        
        # --- Create async tasks for background events ---
        event_tasks = []
        event_map={}
        logger.info(f"[FSM] Gathering events for action {curr_action_id}")
        events = self._gather_events(curr_action_id)
        logger.info(f"[FSM] Gathering events for action {curr_action_id}: {events}")
        for ev_id in events:
            if ev_id == _DONE_EVENT:
                continue
            ev_ir = self.mission.events[ev_id]
            ev_attributes = ev_ir.attributes
            ev_cls = get_event(ev_ir.type_name)
            ev_task = asyncio.create_task(ev_cls(**ev_attributes).check())
            event_tasks.append(ev_task)
            event_map[ev_task] = ev_id
        logger.info(f"[FSM] Event tasks created: {event_tasks}")

        # --- Wait for whichever finishes first ---
        logger.info(f"[FSM] Waiting for action or events to complete...")
        done, pending = await asyncio.wait(
            [action_task] + event_tasks,
            return_when=asyncio.FIRST_COMPLETED
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        if action_task in done:
            try:
                await action_task
            except Exception as e:
                logger.exception("[FSM] Action %s failed", curr_action_id)
                return _TERMINATE
            logger.info("[FSM] Action finished => event=%s", _DONE_EVENT)
            return _DONE_EVENT
        else:
            done_ev_task = next(iter(done))
            try:
                await done_ev_task
            except Exception as e:
                logger.exception("[FSM] Event task failed")
                return _TERMINATE
            return event_map[done_ev_task]
            

    def _gather_events(self, curr_action_id):
        return list(self.transition.get(curr_action_id, {}).keys())