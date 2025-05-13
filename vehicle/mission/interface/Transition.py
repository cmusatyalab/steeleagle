from abc import ABC, abstractmethod
import asyncio
import logging

logger = logging.getLogger(__name__)


def auto_register_unregister(run_func):
    async def wrapper(self, *args, **kwargs):
        await self._register()
        try:
            await run_func(self, *args, **kwargs)
        finally:
            await self._unregister()
    return wrapper

class Transition(ABC):
    def __init__(self, args):
        self.task_id = args['task_id']
        self.trans_active = args['trans_active']
        self.trans_active_lock = args['trans_active_lock']
        self.trigger_event_queue = args['trigger_event_queue']
        self._stop_event = asyncio.Event()
        self._task = None
    
    async def start(self):
        logger.info(f"Starting transition: {self.__class__.__name__}")
        self._task = asyncio.create_task(self.run())

    async def stop(self):
        logger.info(f"Stopping transition: {self.__class__.__name__}")
        self._stop_event.set()
        if self._task:
            await self._task

    def is_alive(self):
        return self._task is not None and not self._task.done()

    async def _trigger_event(self, event):
        logger.info(f"Task {self.task_id}: Triggered event: {event}")
        await self.trigger_event_queue.put((self.task_id, event))

    async def _register(self):
        logger.info(f"Registering transition: {self.__class__.__name__}")
        async with self.trans_active_lock:
            self.trans_active.append(self)

    async def _unregister(self):
        logger.info(f"Unregistering transition: {self.__class__.__name__}")
        async with self.trans_active_lock:
            if self in self.trans_active:
                self.trans_active.remove(self)

    @abstractmethod
    async def run(self):
        """Subclasses implement their loop logic here."""
        pass
