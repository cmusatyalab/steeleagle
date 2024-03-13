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
        self.isTerminated = False

    def terminate(self):
        self.isTerminated = True
        
    async def run(self):
        logger.info('[TaskRunner] Start to manage the task queue')
        try:
            while True:
                # termniate the loop if commanded by mission controller
                if (self.isTerminated):
                    logger.info('[TaskRunner] terminating the task queue')
                    break
                
                # logger.info('[TaskRunner] HI tttt')
                if (not self.taskQueue.empty()):
                    # get the task
                    logger.info('[TaskRunner] Pulling a task off the task queue')
                    self.currentTask = self.taskQueue.get()
                    
                    # execute a task
                    self.taskCoroutinue = asyncio.create_task(self.currentTask.run())
                await asyncio.sleep(0.1)                   
        except asyncio.CancelledError as e:
            logger.info(f"[TaskRunner]: catching the asyncio exception {e} \n")
            raise
        finally:
            self.stop_task()


    def stop_task(self):
        logger.info(f'[TaskRunner] Stopping current task!')
        if self.taskCoroutinue is not None:
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
