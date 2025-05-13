# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

from abc import ABC, abstractmethod
import asyncio
import functools
import logging
from aenum import Enum

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
    def __init__(self, control, data, task_id, trigger_event_queue, task_args):
        self.data = data
        self.control = control
        self.task_id = task_id
        self.task_attributes = task_args.task_attributes
        self.transitions_attributes = task_args.transitions_attributes
        self.trans_active = []
        self.trans_active_lock = asyncio.Lock()
        self.trigger_event_queue = trigger_event_queue

    @abstractmethod
    async def run(self):
        pass

    def get_task_id(self):
        return self.task_id

    async def _exit(self):
        logger.info(f"**************Exiting task {self.task_id}**************")
        await self.stop_trans()
        await self.trigger_event_queue.put((self.task_id, "done"))

    async def stop_trans(self):
        logger.info(f"**************Stopping transitions for task {self.task_id}**************")
        async with self.trans_active_lock:
            await asyncio.gather(*(t.stop() for t in self.trans_active if t.is_alive()))
        logger.info(f"**************All transitions stopped for task {self.task_id}**************")

    @classmethod
    def call_after_exit(cls, func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            try:
                return await func(self, *args, **kwargs)
            finally:
                await self._exit()
        return wrapper
