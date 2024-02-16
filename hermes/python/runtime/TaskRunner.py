import queue
import asyncio
import logging

logger = logging.getLogger()

class TaskRunner():
    def __init__(self, drone):
        self.drone = drone
        # lock the taskCoroutinue for contention?
        self.taskCoroutinue = None
        self.currentTask = None
        # thread safe queue
        self.taskQueue = queue.Queue()

    async def run(self):
        try:
            while True:
                if (not self.taskQueue.empty()):
                    logger.debug('[Mission] Pulling a task off the task queue')
                    self.currentTask = self.taskQueue.get()
                    # execute a task
                    try:
                        self.taskCoroutinue = asyncio.create_task(self.currentTask.run()) 
                        await self.taskCoroutinue
                        self.taskCoroutinue = None
                    except Exception as e:
                        logger.error(f'[Mission] Task exited with error: {e}')
                await asyncio.sleep(0.1)                   
        except Exception as e:
            logger.error(f'[Mission] Exec loop interrupted by exception: {e}')
        finally:
            await self.stop_task()


    async def stop_task(self):
        if self.taskCoroutinue is not None:
            # stop all the transitions of the task
            self.currentTask.stop_trans()
            
            # kill the task
            try:
                await self.taskCoroutinue.cancel()
            except asyncio.CancelledError:
                logger.debug(f'[Mission] Stopped current task!')
                
                
    def push_task(self, task):
        self.taskQueue.put(task)

    def pause(self):
        pass

    def force_task(self, task):
        pass
