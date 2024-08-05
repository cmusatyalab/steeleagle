
from user.project.transition_defs.ObjectDetectionTransition import ObjectDetectionTransition
from user.project.transition_defs.TimerTransition import TimerTransition
from user.project.transition_defs.HSVDetectionTransition import HSVDetectionTransition
from user.project.interface.Task import Task
import asyncio
import ast
import logging
from gabriel_protocol import gabriel_pb2


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class TestTask(Task):

    def __init__(self, drone, cloudlet, task_id, trigger_event_queue, task_args):
        super().__init__(drone, cloudlet, task_id, trigger_event_queue, task_args)
       
        
    def create_transition(self):
        
        logger.info(f"**************Test Task {self.task_id}: create transition! **************\n")
        logger.info(self.transitions_attributes)
        args = {
            'task_id': self.task_id,
            'trans_active': self.trans_active,
            'trans_active_lock': self.trans_active_lock,
            'trigger_event_queue': self.trigger_event_queue
        }
        
        # triggered event
        if ("timeout" in self.transitions_attributes):
            logger.info(f"**************Test Task {self.task_id}:  timer transition! **************\n")
            timer = TimerTransition(args, self.transitions_attributes["timeout"])
            timer.daemon = True
            timer.start()
            
    
    # test all the driver calls        
    @Task.call_after_exit
    async def run(self):
        
        self.create_transition()
        
        # try:
        logger.info(f"**************Test Task {self.task_id}: hi this is Test task {self.task_id}**************\n")

        ''' Streaming methods '''
        await self.drone.getCameras()
        await self.drone.switchCameras()
       
    
        ''' Movement methods '''
        await self.drone.setAttitude()
        await self.drone.setVelocity()
        await self.drone.setRelativePosition()
        await self.drone.setTranslation()
        await self.drone.setGlobalPosition()
        await self.drone.hover()

        logger.info(f"**************Test Task {self.task_id}: Done**************\n")
    
    
    # this is for partol test
    # async def run(self):
        
    #     self.create_transition()
        
    #     # try:
    #     logger.info(f"**************Test Task {self.task_id}: hi this is Test task {self.task_id}**************\n")
    #     coords = ast.literal_eval(self.task_attributes["coords"])
    #     await self.drone.setGimbalPose(0.0, float(self.task_attributes["gimbal_pitch"]), 0.0)
        
    #     for dest in coords:
    #         lng = dest["lng"]
    #         lat = dest["lat"]
    #         alt = dest["alt"]
    #         logger.info(f"**************Test Task {self.task_id}: Move **************\n")
    #         logger.info(f"**************Test Task {self.task_id}: move to {lat}, {lng}, {alt}**************\n")
    #         await self.drone.moveTo(lat, lng, alt)
    #         await asyncio.sleep(0.2)
    #         # await asyncio.sleep(hover_delay)

    #     logger.info(f"**************Test Task {self.task_id}: Done**************\n")


