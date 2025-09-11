from __future__ import annotations
import asyncio
from dsl.compiler.ir import MissionIR
from dsl.compiler.registry import get_action, get_event
import logging


logger = logging.getLogger(__name__)

# need to refine these
_DONE_EVENT = "done"
_TERMINATE = "terminate"

class MissionFSM:
    def __init__(self, mission: MissionIR):
        self.mission = mission
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

        # --- Create async tasks for background events ---
        event_tasks = []
        event_map={}
        for ev_id in self._gather_events(curr_action_id):
            ev_ir = self.mission.events[ev_id]
            ev_attributes = ev_ir.attributes
            ev_cls = get_event(ev_ir.type_name)
            ev_task = asyncio.create_task(ev_cls(**ev_attributes).check())
            event_tasks.append(ev_task)
            event_map[ev_task] = ev_id

        # --- Wait for whichever finishes first ---
        done, pending = await asyncio.wait(
            [action_task] + event_tasks,
            return_when=asyncio.FIRST_COMPLETED
        )

        # --- Cancel leftovers ---
        for task in pending:
            task.cancel()

        # --- Decide result ---
        result_event = None
        if action_task in done:
            result_event = _DONE_EVENT 
            logger.info(f"[FSM] Action finished, event={result_event}")

        else:
            done_ev_task = done.pop() 
            result_event = event_map[done_ev_task]
            logger.info(f"[FSM] Background event triggered: {result_event}")
        
        return result_event 
            

    def _gather_events(self, curr_action_id):
        return [
            ev for (a_id, ev), nxt in self.transitions.items()
            if a_id == curr_action_id
        ]

         
