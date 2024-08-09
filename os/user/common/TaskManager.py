import asyncio
from  user.project.interface.Task import TaskType      
from user.project.task_defs.TrackTask import TrackTask
from user.project.task_defs.DetectTask import DetectTask
from user.project.task_defs.AvoidTask import AvoidTask
from user.project.task_defs.TestTask import TestTask
import queue
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

    
class TaskManager():
    
    def __init__(self, drone, compute, transit_map, task_arg_map):
        super().__init__()
        self.trigger_event_queue = queue.Queue()
        self.drone = drone
        self.compute = compute
        self.start_task_id = None
        self.curr_task_id = None
        self.transit_map = transit_map
        self.task_arg_map = task_arg_map
        
        
        self.currentTask = None
        self.taskCurrentCoroutinue = None

    ######################################################## TASK #############################################################
    def get_current_task(self):
        return self.curr_task_id
            
    def retrieve_next_task(self, current_task_id, triggered_event):
        logger.info(f"TaskManager: next task, current_task_id {current_task_id}, trigger_event {triggered_event}")
        try:
            next_task_id  = self.transit_map.get(current_task_id)(triggered_event)
        except Exception as e:
            logger.info(f"{e}")
                
        logger.info(f"TaskManager: next_task_id {next_task_id}")
        return next_task_id
    
    def transit_task_to(self, task):
        logger.info(f"TaskManager: transit to task with task_id: {task.task_id}, current_task_id: {self.curr_task_id}")
        self.stop_task()
        self.start_task(task)
        self.curr_task_id = task.task_id
    
    async def init_task(self):
        logger.info('TaskManager: init task')
        self.start_task_id = self.retrieve_next_task("start", None)
        logger.info('TaskManager: create start task')
        start_task = self.create_task(self.start_task_id)
        if start_task != None:
            # set the current task
            self.curr_task_id = start_task.task_id
            logger.info(f"TaskManager: start task, current taskid:{self.curr_task_id}\n")
            
            
            # takeoff
            logger.info("TaskManager: taking off")
            await self.drone.takeOff()
            
            # start
            self.start_task(start_task)
    
    def create_task(self, task_id):
        logger.info(f'TaskManager: taskid{task_id}')
        if (task_id in self.task_arg_map.keys()):
            if (self.task_arg_map[task_id].task_type == TaskType.Detect):
                logger.info('TaskManager: Detect task')
                return DetectTask(self.drone, self.compute, task_id, self.trigger_event_queue, self.task_arg_map[task_id])
            elif (self.task_arg_map[task_id].task_type == TaskType.Track):
                logger.info('TaskManager: Track task')
                return TrackTask(self.drone, self.compute, task_id, self.trigger_event_queue, self.task_arg_map[task_id])
            elif (self.task_arg_map[task_id].task_type == TaskType.Avoid):
                logger.info('TaskManager: Avoid task')
                return AvoidTask(self.drone, self.compute, task_id, self.trigger_event_queue, self.task_arg_map[task_id])
            elif (self.task_arg_map[task_id].task_type == TaskType.Test):
                logger.info('TaskManager: Test task')
                return TestTask(self.drone, None, task_id, self.trigger_event_queue, self.task_arg_map[task_id])
        return None
    
    def stop_task(self):
        logger.info(f'TaskManager: Stopping current task!')
        if self.taskCurrentCoroutinue:
            # stop all the transitions of the task
            self.currentTask.stop_trans()
            logger.info(f'TaskManager: transitions in the current task stopped!')
            
            is_canceled = self.taskCurrentCoroutinue.cancel()
            if is_canceled:
                logger.info(f'TaskManager:  task cancelled successfully')
                
    def start_task(self, task):
        logger.info(f'TaskManager: start the task! task: {str(task)}')
        self.currentTask = task
        self.taskCurrentCoroutinue = asyncio.create_task(self.currentTask.run())
        logger.info(f'TaskManager: started the task! task: {str(task)}')

    def pause_task(self):
        pass

    def force_task(self, task):
        pass

    ######################################################## MAIN LOOP ############################################################
    async def run(self):
        try:
            # start the mc
            logger.info("TaskManager: start the manager\n")
            await self.init_task()
            
            # main
            logger.info("TaskManager: go to the loop routine\n")
            while True:
                # logger.info("TM")
                # logger.info("TaskManager: loop routine\n")
                if (not self.trigger_event_queue.empty()):
                    item = self.trigger_event_queue.get()
                    task_id = item[0]
                    trigger_event = item[1]
                    logger.info(f"TaskManager: Trigger one event! \n")
                    logger.info(f"TaskManager: Task id  {task_id} \n")
                    logger.info(f"TaskManager: event   {trigger_event} \n")
                    if (task_id == self.get_current_task()):
                        next_task_id = self.retrieve_next_task(task_id, trigger_event)
                        if (next_task_id == "terminate"):
                            break
                        else:
                            next_task = self.create_task(next_task_id)
                            logger.info(f"TaskManager: task created  taskid {str(next_task.task_id)} \n")
                            self.transit_task_to(next_task, self.tr)

                await asyncio.sleep(0)            

        except Exception as e:
            logger.info(f"TaskManager: catching the exception {e} \n")
        finally:
            # stop the current task
            self.stop_task()
            #end the tr
            logger.info("TaskManager: terminate the manager\n")

    
