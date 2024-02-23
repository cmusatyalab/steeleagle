import queue
import asyncio
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class TaskRunner():
    def __init__(self, drone):
        self.drone = drone
        # lock the taskCoroutinue for contention?
        self.taskCoroutinue = None
        self.currentTask = None
        # thread safe queue
        self.taskQueue = queue.Queue()

    async def run(self):
        logger.info('[TaskRunner] Start to manage the task queue')
        try:
            while True:
                logger.info('[TaskRunner] HI tttt')
                if (not self.taskQueue.empty()):
                    # get the task
                    logger.info('[TaskRunner] Pulling a task off the task queue')
                    self.currentTask = self.taskQueue.get()
                    
                    # execute a task
                    self.taskCoroutinue = asyncio.create_task(self.currentTask.run()) 
                    await self.taskCoroutinue
                    logger.info('[TaskRunner] Finish executing one task off the task queue')
                    self.taskCoroutinue = None

                await asyncio.sleep(0.1)                   
        except asyncio.CancelledError as e:
            logger.info(f'[TaskRunner] Exec loop interrupted by exception: {e}')
        finally:
            await self.stop_task()


    async def stop_task(self):
        
        if self.taskCoroutinue is not None:
            logger.info(f'[TaskRunner] Stopping current task!')
            # stop all the transitions of the task
            self.currentTask.stop_trans()
            logger.info(f'[TaskRunner]  transitions in the current task stopped!')
            
            is_canceled = self.taskCoroutinue.cancel()
            if is_canceled:
                logger.info(f'[TaskRunner]  task cancelled successfully')
                
                
                
    def push_task(self, task):
        logger.info(f'[TaskRunner] push the task! task: {str(task)}')
        
        self.taskQueue.put(task)

    def pause(self):
        pass

    def force_task(self, task):
        pass
