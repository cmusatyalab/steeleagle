

from interfaces.FlightScript import FlightScript
import asyncio
import logging
# Import derived tasks
from task_defs.DetectTask import DetectTask

logger = logging.getLogger()

class MS(FlightScript):
   
    def __init__(self, drone, cloudlet):
        super().__init__(drone, cloudlet)
 
    async def run(self):
        try:
            kwargs = {}
            # Polygon 1/DetectTask START
            kwargs.clear()
            kwargs["gimbal_pitch"] = "-45.0"
            kwargs["drone_rotation"] = "0.0"
            kwargs["sample_rate"] = "2"
            kwargs["hover_delay"] = "0"
            kwargs["model"] = "coco"
            kwargs["coords"] = "[{'lng': -79.9504026, 'lat': 40.4158087, 'alt': 25.0}, {'lng': -79.9494558, 'lat': 40.4133265, 'alt': 25.0}, {'lng': -79.9481307, 'lat': 40.4136072, 'alt': 25.0}, {'lng': -79.9490977, 'lat': 40.4160665, 'alt': 25.0}, {'lng': -79.9504026, 'lat': 40.4158087, 'alt': 25.0}]"
            t = DetectTask(self.drone, self.cloudlet, **kwargs)
            self.taskQueue.put(t)
            logger.debug('[Mission] Added task DetectTask to the queue')
            
            logger.debug('[Mission] Directing the drone to take off')
            await self.drone.takeOff()
            logger.debug('[Mission] Starting the exec loop')
            await self.execLoop()
        except Exception as e:
            print(e)