import queue
import asyncio
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class TaskRunner():
    def __init__(self, drone):
        self.drone = drone
        self.taskCoroutinue = None
        self.currentTask = None
        self.taskQueue = queue.Queue()
    
    async def run(self):
        logger.info('[TaskRunner] Start executing the task queue')
        try:
            while True:
                try:
                    # Get the current task, if it exists.
                    self.currentTask = self.taskQueue.get_nowait()
                    # If we get here without throwing an exception, we have a new task!
                    logger.info('[TaskRunner] Pulling a task off the task queue')
                    
                    # Execute the task
                    # We don't wait on this task to complete so that we can stop it
                    # independently without causing a CancelledError.
                    self.taskCoroutinue = asyncio.create_task(self.currentTask.run())
                except queue.Empty:
                    await asyncio.sleep(0.5)                   
        except asyncio.CancelledError as e:
            self.stop_task()

        logger.info(f'[TaskRunner] Stopped!')

    def stop_task(self):
        logger.info(f'[TaskRunner] Stopping current task!')
        if self.taskCoroutinue is not None:
            # Stop all the transitions of the task
            self.currentTask.stop_trans()
            logger.info(f'[TaskRunner] Transitions for the current task stopped!')
            
            self.taskCoroutinue.cancel()
            logger.info(f'[TaskRunner] Current task cancelled.')
                
    def queue_task(self, task):
        logger.info(f'[TaskRunner] Queueing task: {str(task)}')
        self.taskQueue.put(task)

    def pause_task(self):
        raise NotImplemented()

    def force_task(self, task):
        logger.info(f'[TaskRunner] Forcing new task: {str(task)}')
        self.stop_task()
        self.queue_task(task)
