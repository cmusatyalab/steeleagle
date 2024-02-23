import asyncio
from  interfaces.Task import TaskType      
from task_defs.TrackTask import TrackTask
from task_defs.DetectTask import DetectTask
from mission.MissionCreator import MissionCreator
from mission.TaskRunner import TaskRunner
import queue
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

    
class MissionController():

    @staticmethod
    def default_transit(triggered_event):
        logger.info(f"MissionController: no matched up transition, triggered event {triggered_event}\n", triggered_event)
        
    def __init__(self, drone, cloudlet):
        super().__init__()
        self.trigger_event_queue = queue.Queue()
        self.drone = drone
        self.cloudlet = cloudlet
        self.start_task_id = None
        self.curr_task_id = None
        self.transitMap = {}
        self.transitMap["default"]= self.default_transit
        self.task_arg_map = {}

    ######################################################## TASK #############################################################
    def create_task(self, task_id):
        logger.info(f'MC: taskid{task_id}')
        if (task_id in self.task_arg_map.keys()):
            if (self.task_arg_map[task_id].task_type == TaskType.Detect):
                logger.info('MC: Detect task')
                return DetectTask(self.drone, self.cloudlet, task_id, self.trigger_event_queue, self.task_arg_map[task_id])
            elif (self.task_arg_map[task_id].task_type == TaskType.Track):
                logger.info('MC: Track task')
                return TrackTask(self.drone, self.cloudlet, task_id, self.trigger_event_queue, self.task_arg_map[task_id])
        return None
            
    def next_task(self, current_task_id, triggered_event):
        logger.info(f"MC next task, current_task_id {current_task_id}, trigger_event {triggered_event}")
        try:
            next_task_id  = self.transitMap.get(current_task_id, self.default_transit)(triggered_event)
        except Exception as e:
            logger.info(f"{e}")
                
        logger.info(f"next_task_id {next_task_id}")
        return next_task_id
    

    ######################################################## MISSION ############################################################    
    async def start_mission(self, tr):
        logger.info('MC: Start mission')
        self.start_task_id = self.next_task("start", None)
        logger.info('MC: Create task')
        start_task = self.create_task(self.start_task_id)
        logger.info('MC: Got task, starting...')
        if start_task != None:
            # set the current task
            self.curr_task_id = start_task.task_id
            logger.info(f"MC: start mission, current taskid:{self.curr_task_id}\n")
            
            # takeoff
            await self.drone.takeOff()
            logger.info("MC: taking off")
            
            # start
            tr.push_task(start_task)
            
       
    async def transit_to(self, task, tr):
        logger.info(f"MC: transit to task with task_id: {task.task_id}, current_task_id: {self.curr_task_id}")
        tr.stop_task()
        tr.push_task(task)
        self.curr_task_id = task.task_id
       
    async def end_mission(self):
        logger.info("MC: end mission, rth\n")
        await self.drone.rth()
        
    def get_current_task(self):
        return self.curr_task_id
    
    ######################################################## CONTROL ############################################################
     
    async def run(self):
        # start the mc
        logger.info("MissionController: hi start the controller\n")

        logger.info("MissionController: define mission \n")
        MissionCreator.define_mission(self.transitMap, self.task_arg_map)
        logger.info(f"MissionController: transitMap {str(self.transitMap)} \n")
        logger.info(f"MissionController: task_arg_map {str(self.task_arg_map)} \n")
        
        logger.info("MissionController: create TaskRunner \n")
        tr = TaskRunner(self.drone)
        tr_coroutine = asyncio.create_task(tr.run())
        
        logger.info("MissionController: start mission \n")
        await self.start_mission(tr)
        
        logger.info("MissionController: go to the inf loop routine\n")
        # main logic check the triggered event
        while True:
            # logger.info('[MC] HI tttt')
            
            if (not self.trigger_event_queue.empty()):
                item = self.trigger_event_queue.get()
                task_id = item[0]
                trigger_event = item[1]
                logger.info(f"MissionController: Trigger one event! \n")
                logger.info(f"MissionController: Task id  {task_id} \n")
                logger.info(f"MissionController: event   {trigger_event} \n")
                if (task_id == self.get_current_task()):
                    next_task_id = self.next_task(task_id, trigger_event)
                    if (next_task_id == "terminate"):
                        break
                    else:
                        next_task = self.create_task(next_task_id)
                        logger.info(f"MissionController: task created  taskid {str(next_task.task_id)} \n")
                        await self.transit_to(next_task, tr)
                        
            await asyncio.sleep(0.1)
        
        # terminate the tr
        logger.info("MissionController: terminating TaskRunner \n")
        tr.terminate()
        await tr_coroutine
        logger.info("MissionController: terminated TaskRunner \n")
        
        # terminate the mr
        logger.info(f"MissionController: the current task is done, end mission \n")
        await self.end_mission()
        
        #end the mc
        logger.info("MissionController: terminate the controller\n")







