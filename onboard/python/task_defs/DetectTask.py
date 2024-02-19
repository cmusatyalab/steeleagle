
from transition_defs.TransObjectDetection import TransObjectDetection
from transition_defs.TransTimer import TransTimer
from interfaces.Task import Task
import asyncio
import ast
import logging
from gabriel_protocol import gabriel_pb2


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class DetectTask(Task):

    def __init__(self, drone, cloudlet, task_id, trigger_event_queue, task_args):
        super().__init__(drone, cloudlet, task_id, trigger_event_queue, task_args)
       
        
    def create_transition(self):
        
        logger.debug(f"**************Detect Task {self.task_id}: create transition! **************\n")
        logger.debug(self.transitions_attributes)
        args = {
            'task_id': self.task_id,
            'trans_active': self.trans_active,
            'trans_active_lock': self.trans_active_lock,
            'trigger_event_queue': self.trigger_event_queue
        }
        
        # triggered event
        if ("timeout" in self.transitions_attributes):
            logger.debug(f"**************Detect Task {self.task_id}:  timer transition! **************\n")
            timer = TransTimer(args, self.transitions_attributes["timeout"])
            timer.daemon = True
            timer.start()
            
        if ("object_detection" in self.transitions_attributes):
            logger.debug(f"**************Detect Task {self.task_id}:  object detection transition! **************\n")
            self.cloudlet.clearResults("openscout-object")
            object_trans = TransObjectDetection(args, self.transitions_attributes["object_detection"], self.cloudlet)
            object_trans.daemon = True
            object_trans.start()
            
    async def run(self):
        # init the cloudlet
        self.cloudlet.switchModel(self.task_attributes["model"])
        
        self.create_transition()
        
        try:
            logger.debug(f"**************Detect Task {self.task_id}: hi this is detect task {self.task_id}**************\n")
            coords = ast.literal_eval(self.task_attributes["coords"])
            await self.drone.setGimbalPose(0.0, float(self.task_attributes["gimbal_pitch"]), 0.0)
            hover_delay = int(self.task_attributes["hover_delay"])
            for dest in coords:
                lng = dest["lng"]
                lat = dest["lat"]
                alt = dest["alt"]
                logger.debug(f"**************Detect Task {self.task_id}: Move **************\n")
                logger.debug(f"**************Detect Task {self.task_id}: move to {lat}, {lng}, {alt}**************\n")
                await self.drone.moveTo(lat, lng, alt)
                await asyncio.sleep(hover_delay)

            logger.debug(f"**************Detect Task {self.task_id}: Done**************\n")
            self._exit()
        except Exception as e:
            print(e)


