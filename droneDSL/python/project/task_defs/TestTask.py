
from ..transition_defs.TimerTransition import TimerTransition
from interface.Task import Task
import asyncio
import ast
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class TestTask(Task):

    def __init__(self, drone, cloudlet, task_id, trigger_event_queue, task_args):
        super().__init__(drone, cloudlet, task_id, trigger_event_queue, task_args)
       
        
    def create_transition(self):
        
        logger.info(f"**************Test Task 2{self.task_id}: create transition! **************\n")
        logger.info(self.transitions_attributes)
        args = {
            'task_id': self.task_id,
            'trans_active': self.trans_active,
            'trans_active_lock': self.trans_active_lock,
            'trigger_event_queue': self.trigger_event_queue
        }
        
        # triggered event
        if ("timeout" in self.transitions_attributes):
            logger.info(f"**************Test Task 2{self.task_id}:  timer transition! **************\n")
            timer = TimerTransition(args, self.transitions_attributes["timeout"])
            timer.daemon = True
            timer.start()
            
    
    # test all the driver calls        
    @Task.call_after_exit
    async def run(self):
        
        # self.create_transition()
        
        logger.info(f"**************Test Task 2{self.task_id}: hi this is Test task2 {self.task_id}**************\n")
    
        # coords = [
        #     {"lat": 37.7749, "lng": -122.4194, "alt": 30, "bear": 0},  # San Francisco
        #     {"lat": 34.0522, "lng": -118.2437, "alt": 50, "bear": 0},  # Los Angeles
        #     {"lat": 40.7128, "lng": -74.0060, "alt": 100, "bear": 0}   # New York
        # ]
        while True:
            
            avoid_res = await self.cloudlet.getResults('obstacle-avoidance')
            detect_res = await self.cloudlet.getResults('openscout-object')
            
            logger.info(f"**************Test Task 2{self.task_id}: Avoidance Result: {avoid_res}**************\n")
            logger.info(f"**************Test Task 2{self.task_id}: Detection Result: {detect_res}**************\n")
        
        coords = ast.literal_eval(self.task_attributes["coords"])

        logger.info(f"**************Test Task 2{self.task_id}: hi this is Test task2 {self.task_id}**************\n")
        for dest in coords:
            lng = dest["lng"]
            lat = dest["lat"]
            alt = dest["alt"]
            # bear = dest["bear"]
            bear = 0
            logger.info(f"**************Test Task 2{self.task_id}: setGPSLocation **************\n")
            logger.info(f"**************Test Task 2{self.task_id}: GPSLocation: {lat}, {lng}, {alt} {bear}**************\n")
            await self.drone.setGPSLocation(lat, lng, alt, bear)
            await asyncio.sleep(0)
        
        

        logger.info(f"**************Test Task 2{self.task_id}: Done**************\n")
            
        


