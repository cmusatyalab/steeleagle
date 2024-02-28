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
        
    def __init__(self, drone, cloudlet):
        super().__init__()
        self.trigger_event_queue = queue.Queue()
        self.drone = drone
        self.cloudlet = cloudlet
        self.start_task_id = None
        self.curr_task_id = None
        self.transitMap = {}
        self.transitMap["default"] = MissionCreator.default_transit
        self.task_arg_map = {}

    def create_task(self, task_id):
        if (task_id in self.task_arg_map.keys()):
            if (self.task_arg_map[task_id].task_type == TaskType.Detect):
                return DetectTask(self.drone, self.cloudlet, task_id, self.trigger_event_queue, self.task_arg_map[task_id])
            elif (self.task_arg_map[task_id].task_type == TaskType.Track):
                return TrackTask(self.drone, self.cloudlet, task_id, self.trigger_event_queue, self.task_arg_map[task_id])
        return None
            
    def next_task(self, current_task_id, triggered_event):
        try:
            next_task_id  = self.transitMap.get(current_task_id, MissionCreator.default_transit)(triggered_event)
        except Exception as e:
            logger.info(f"{e}")
                
        return next_task_id
    
    async def start_mission(self, tr):
        self.start_task_id = self.next_task("start", None)
        start_task = self.create_task(self.start_task_id)
        if start_task != None:
            # Set the current task
            self.curr_task_id = start_task.task_id
            
            # Takeoff
            await self.drone.takeOff()
            
            # Start
            tr.queue_task(start_task)
            
       
    async def transit_to(self, task, tr):
        logger.info(f"[MissionController] Transiting to task: {task.task_id} from current task: {self.curr_task_id}")
        tr.force_task(task)
        self.curr_task_id = task.task_id
       
    async def end_mission(self):
        logger.info("[MissionController] End of mission, returning home!")
        await self.drone.rth()
        
    def get_current_task(self):
        return self.curr_task_id
    
    async def run(self):
        try:
            # Start the MissionController
            logger.info("[MissionController] Starting the MissionController")

            MissionCreator.define_mission(self.transitMap, self.task_arg_map)
            tr = TaskRunner(self.drone)
            tr_coroutine = asyncio.create_task(tr.run())
            await self.start_mission(tr)
            
            while True:
                try:
                    item = self.trigger_event_queue.get_nowait()
                    task_id = item[0]
                    trigger_event = item[1]
                    logger.info(f"[MissionController] Event triggered: {trigger_event}")
                    if (task_id == self.get_current_task()):
                        next_task_id = self.next_task(task_id, trigger_event)
                        if (next_task_id == "terminate"):
                            break
                        else:
                            next_task = self.create_task(next_task_id)
                            logger.info(f"[MissionController] Task created: {str(next_task.task_id)} \n")
                            await self.transit_to(next_task, tr)
                except queue.Empty:
                    await asyncio.sleep(0.1)            

        except asyncio.CancelledError as e:
            logger.info(f"MissionController: catching the asyncio exception {e} \n")
        finally:
            # Terminate the TaskRunner
            logger.info("MissionController: terminating TaskRunner")
            tr_coroutine.cancel()
