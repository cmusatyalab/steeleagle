import queue
import threading
import ctypes
import queue
import asyncio
import logging

logger = logging.getLogger()

class FlightScript():

    def __init__(self, drone, cloudlet):
        self.drone = drone
        # lock the taskthread for contention?
        self.taskThread = None
        
        # thread safe queue
        self.taskQueue = queue.Queue()

    async def execLoop(self):
        try:
            while not self.taskQueue.empty():
                logger.debug('[Mission] Pulling a task off the task queue')
                await self.exec(self.taskQueue.get())
        except Exception as e:
            logger.error(f'[Mission] Exec loop interrupted by exception: {e}')
        finally:
            await self.stop()

    async def exec(self, task):
        try:
            self.currentTask = task
            self.taskThread = asyncio.create_task(self.currentTask.run()) 
            await self.taskThread
            self.taskThread = None
        except Exception as e:
            logger.error(f'[Mission] Task exited with error: {e}')

    async def stop(self):
        self.taskQueue = queue.Queue() # Clear the queue
        if self.taskThread is not None:
            self.taskThread.cancel()
            try:
                await self.taskThread
            except asyncio.CancelledError:
                logger.debug(f'[Mission] Stopped current task!')

    def pause(self):
        pass

    def push_task(self, task):
        self.taskQueue.put(task)

    def force_task(self, task):
        pass
