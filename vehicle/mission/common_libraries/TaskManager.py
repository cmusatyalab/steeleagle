import asyncio
import interface.Task as taskitf     
import project.task_defs.TrackTask as track 
import project.task_defs.DetectTask as detect
import project.task_defs.AvoidTask as avoid
import project.task_defs.TestTask as test
import queue
import logging

logger = logging.getLogger(__name__)

    
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
        logger.info(f"next task, current_task_id {current_task_id}, trigger_event {triggered_event}")
        try:
            next_task_id  = self.transit_map.get(current_task_id)(triggered_event)
        except Exception as e:
            logger.info(f"{e}")
                
        logger.info(f"next_task_id {next_task_id}")
        return next_task_id
    
    def transit_task_to(self, task):
        logger.info(f"transit to task with task_id: {task.task_id}, current_task_id: {self.curr_task_id}")
        self.stop_task()
        self.start_task(task)
        self.curr_task_id = task.task_id
    
    async def init_task(self):
        logger.info('init task')
        self.start_task_id = self.retrieve_next_task("start", None)
        logger.info('create start task')
        start_task = self.create_task(self.start_task_id)
        if start_task != None:
            # set the current task
            self.curr_task_id = start_task.task_id
            logger.info(f"start task, current taskid:{self.curr_task_id}\n")
            
            
            # takeoff
            logger.info("taking off")
            await self.drone.takeOff()
            
            # start
            self.start_task(start_task)
    
    def create_task(self, task_id):
        logger.info(f'taskid{task_id}')
        if (task_id in self.task_arg_map.keys()):
            if (self.task_arg_map[task_id].task_type == taskitf.TaskType.Detect):
                logger.info('Detect task')
                return detect.DetectTask(self.drone, self.compute, task_id, self.trigger_event_queue, self.task_arg_map[task_id])
            elif (self.task_arg_map[task_id].task_type == taskitf.TaskType.Track):
                logger.info('Track task')
                return track.TrackTask(self.drone, self.compute, task_id, self.trigger_event_queue, self.task_arg_map[task_id])
            elif (self.task_arg_map[task_id].task_type == taskitf.TaskType.Avoid):
                logger.info('Avoid task')
                return avoid.AvoidTask(self.drone, self.compute, task_id, self.trigger_event_queue, self.task_arg_map[task_id])
            elif (self.task_arg_map[task_id].task_type == taskitf.TaskType.Test):
                logger.info('Test task')
                return test.TestTask(self.drone, self.compute, task_id, self.trigger_event_queue, self.task_arg_map[task_id])
        return None
    
    def stop_task(self):
        logger.info(f'Stopping current task!')
        if self.taskCurrentCoroutinue:
            # stop all the transitions of the task
            self.currentTask.stop_trans()
            logger.info(f'transitions in the current task stopped!')
            
            is_canceled = self.taskCurrentCoroutinue.cancel()
            if is_canceled:
                logger.info(f' task cancelled successfully')
                
    def start_task(self, task):
        logger.info(f'start the task! task: {str(task)}')
        self.currentTask = task
        self.taskCurrentCoroutinue = asyncio.create_task(self.currentTask.run())
        logger.info(f'started the task! task: {str(task)}')

    def pause_task(self):
        pass

    def force_task(self, task):
        pass

    ######################################################## MAIN LOOP ############################################################
    async def run(self):
        try:
            # start the mc
            logger.info("start the manager\n")
            await self.init_task()
            
            # main
            logger.info("go to the loop routine\n")
            while True:
                # logger.info("TM")
                # logger.info("loop routine\n")
                if (not self.trigger_event_queue.empty()):
                    item = self.trigger_event_queue.get()
                    task_id = item[0]
                    trigger_event = item[1]
                    logger.info(f"Trigger one event! \n")
                    logger.info(f"Task id  {task_id} \n")
                    logger.info(f"event   {trigger_event} \n")
                    if (task_id == self.get_current_task()):
                        next_task_id = self.retrieve_next_task(task_id, trigger_event)
                        if (next_task_id == "terminate"):
                            break
                        else:
                            next_task = self.create_task(next_task_id)
                            logger.info(f"task created  taskid {str(next_task.task_id)} \n")
                            self.transit_task_to(next_task)

                await asyncio.sleep(0)            

        except Exception as e:
            logger.info(f"catching the exception {e} \n")
        finally:
            # stop the current task
            self.stop_task()
            #end the tr
            logger.info("terminate the manager\n")

    
