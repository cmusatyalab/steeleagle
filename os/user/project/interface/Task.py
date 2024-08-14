# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

from abc import ABC, abstractmethod
import functools
import logging
import threading
from aenum import Enum
import inspect

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class TaskType(Enum):
    Detect = 1
    Track = 2
    Avoid = 3
    Test = 4

class TaskArguments():
    def __init__(self, task_type, transitions_attributes, task_attributes):
        self.task_type = task_type
        self.task_attributes = task_attributes
        self.transitions_attributes = transitions_attributes
        
class Task(ABC):

    def __init__(self, drone, cloudlet, task_id, trigger_event_queue, task_args):
        self.cloudlet = cloudlet
        self.drone = drone
        self.task_attributes = task_args.task_attributes
        self.transitions_attributes = task_args.transitions_attributes
        self.task_id = task_id
        self.trans_active =  []
        self.trans_active_lock = threading.Lock()
        self.trigger_event_queue = trigger_event_queue

    @abstractmethod
    async def run(self):
        pass

    def get_task_id(self):
        return self.task_id


    def _exit(self):
        # kill all the transitions
        logger.info(f"**************exit the task**************\n")
        self.stop_trans()
        self.trigger_event_queue.put((self.task_id,  "done"))
        
    def stop_trans(self):
        logger.info(f"**************stopping the transitions**************\n")
        for trans in self.trans_active:
            if trans.is_alive():
                trans.stop()
                trans.join()
        logger.info(f"**************the transitions stopped**************\n")
        
        
    @classmethod
    def call_after_exit(cls, func):
        """Decorator to call _exit after the decorated function completes."""
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            try:
                # Call the decorated function
                result = await func(self, *args, **kwargs)
                return result
            finally:
                # Ensure _exit is called after the function completes
                self._exit()

        return wrapper
        
    def pause(self):
        pass
    
    def resume(self):
        pass
