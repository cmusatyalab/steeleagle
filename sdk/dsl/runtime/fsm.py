from __future__ import annotations
import asyncio
import contextlib
from typing import Dict, Tuple
from compiler.ir import MissionIR
from compiler.registry import get_action, get_event
import logging


logger = logging.getLogger(__name__)
_DONE_EVENT = "done"
_TERMINATE = "terminate"
class MissionFSM:
    def __init__(self, mission: MissionIR):
        self.mission = mission
        self.transition = mission.transitions
        
    async def run(self):
        # get the start action
        start_action_id = self.mission.start_action_id
        state = start_action_id
        while (state != _TERMINATE):
            result_event = await self.run_state(state, context)
            next_state = self.transition[state][result_event]
            state = next_state
            
    async def run_state(self, curr_action_id, context):
        action_ir = self.mission.actions[curr_action_id]
        action_cls = get_action(action_ir.type_name)
        action = action_cls(**action_ir.attributes)

        self.logger(f"[FSM] Entering state={curr_action_id}")

        # --- Create async task for the action itself ---
        action_task = asyncio.create_task(action.run(context))

        # --- Create async tasks for background events ---
        event_tasks = []
        event_map={}
        for ev_id in self._gather_events(curr_action_id):
            ev_ir = self.mission.events[ev_id]
            ev_attributes = ev_ir.attributes
            ev_cls = get_event(ev)
            ev_task = asyncio.create_task(ev_cls(**ev_attributes).check(context))
            event_tasks.append(ev_task)
            event_map[ev_task] = ev_id

        # --- Wait for whichever finishes first ---
        done, pending = await asyncio.wait(
            [action_task +  event_tasks],
            return_when=asyncio.FIRST_COMPLETED
        )

        # --- Cancel leftovers ---
        for task in pending:
            task.cancel()

        # --- Decide result ---
        result_event = None
        if action_task in done:
            result_event = _DONE_EVENT 
            self.logger(f"[FSM] Action finished, event={result_event}")

        else:
            done_ev_task = done.pop() 
            result_event = event_map[done_ev_task]
            self.logger(f"[FSM] Background event triggered: {done_ev_id}")
        
        return result_event 
            

    def _gather_events(self, curr_action_id):
        return [
            ev for (a_id, ev), nxt in self.transitions.items()
            if a_id == curr_action_id
        ]

         
