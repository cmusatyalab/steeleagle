import asyncio
from  interfaces.Task import TaskType      
from task_defs.TrackTask import TrackTask
from task_defs.DetectTask import DetectTask
from runtime.MissionCreator import MissionCreator
from runtime.TaskRunner import TaskRunner
import queue
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

    
class MissionController():

    @staticmethod
    def default_transit(triggered_event):
        logger.debug(f"MissionController: no matched up transition, triggered event {triggered_event}\n", triggered_event)
        
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
        logger.debug(f'MC: taskid{task_id}')
        if (task_id in self.task_arg_map.keys()):
            if (self.task_arg_map[task_id].task_type == TaskType.Detect):
                logger.debug('MC: Detect task')
                return DetectTask(self.drone, self.cloudlet, task_id, self.trigger_event_queue, self.task_arg_map[task_id])
            elif (self.task_arg_map[task_id].task_type == TaskType.Track):
                logger.debug('MC: Track task')
                return TrackTask(self.drone, self.cloudlet, task_id, self.trigger_event_queue, self.task_arg_map[task_id])
        return None
            
    def next_task(self, current_task_id, triggered_event):
        logger.debug(f"MC next task, current_task_id {current_task_id}, trigger_event {triggered_event}")
        try:
            next_task_id  = self.transitMap.get(current_task_id, self.default_transit)(triggered_event)
        except Exception as e:
            logger.debug(f"{e}")
                
        logger.debug(f"next_task_id {next_task_id}")
        return next_task_id
    

    ######################################################## MISSION ############################################################    
    async def start_mission(self, tr):
        logger.debug('MC: Start mission')
        self.start_task_id = self.next_task("start", None)
        logger.debug('MC: Create task')
        start_task = self.create_task(self.start_task_id)
        logger.debug('Got task, starting...')
        if start_task != None:
            # set the current task
            self.curr_task_id = start_task.task_id
            logger.debug(f"MC: start mission, current taskid:{self.curr_task_id}\n")
            
            # takeoff
            await self.drone.takeOff()
            logger.debug("MC: taking off")
            
            # start
            tr.push_task(start_task)
            
       
    async def transit_to(self, task, tr):
        logger.debug(f"MC: transit to task with task_id: {task.task_id}, current_task_id: {self.curr_task_id}")
        await tr.stop_task()
        tr.push_task(task)
        self.curr_task_id = task.task_id
       
    async def end_mission(self):
        logger.debug("MC: end mission, rth\n")
        await self.drone.moveTo(40.4156235, -79.9504726 , 20)
        logger.debug("MC: land")
        await self.drone.land()
        
    def get_current_task(self):
        return self.curr_task_id
    
    ######################################################## CONTROL ############################################################
     
    async def run(self):
        # start the mc
        logger.debug("MissionController: hi start the controller\n")

        logger.debug("MissionController: define mission \n")
        MissionCreator.define_mission(self.transitMap, self.task_arg_map)
        logger.debug(f"MissionController: transitMap {str(self.transitMap)} \n")
        logger.debug(f"MissionController: task_arg_map {str(self.task_arg_map)} \n")
        
        logger.debug("MissionController: create TaskRunner \n")
        tr = TaskRunner(self.drone)
        tr_coroutine = asyncio.create_task(tr.run())
        
        logger.debug("MissionController: start mission \n")
        await self.start_mission(tr)
        
        logger.debug("MissionController: go to the inf loop routine\n")
        # main logic check the triggered event
        while True:
            logger.debug('[MC] HI tttt')
            
            if (not self.trigger_event_queue.empty()):
                item = self.trigger_event_queue.get()
                task_id = item[0]
                trigger_event = item[1]
                logger.debug(f"MissionController: Trigger one event! \n")
                logger.debug(f"MissionController: Task id  {task_id} \n")
                logger.debug(f"MissionController: event   {trigger_event} \n")
                if (task_id == self.get_current_task()):
                    next_task_id = self.next_task(task_id, trigger_event)
                    if (next_task_id == "terminate"):
                        break
                    else:
                        next_task = self.create_task(next_task_id)
                        logger.debug(f"MissionController: task created  taskid {next_task_id} \n")
                        await self.transit_to(next_task)
                        
            await asyncio.sleep(0.1)

        # terminate the mr
        logger.debug(f"MissionController: the current task is done, terminate the MISSION RUNNER \n")
        await self.end_mission()
        
        logger.debug("MissionController: terminate TaskRunner \n")
        await tr_coroutine.cancel()
        
        #end the mc
        logger.debug("MissionController: terminate the controller\n")







