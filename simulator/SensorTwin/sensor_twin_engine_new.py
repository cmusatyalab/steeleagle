import time
import asyncio
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class SensorTwinEngine():
    def __init__(self, args):
        self.active = True
        self.origin = None
        self.detection_object_list = None
        self.viewport_list = None
        self.telemetry_retriever = None

        asyncio.run(self.event_loop(update_interval=1))

    async def event_loop(self, update_interval):
        while self.active:
            t_start = time.time()
            await self.process_viewports()
            # detection check and image return for all viewports
            # sleep for update_interval - time elapsed since start
            await asyncio.sleep(update_interval - (time.time() - t_start))

    async def update_viewport(self, drone_id):
        '''
        Asynchronous update for individual viewport objects representing individual drones
        '''
        pass

    async def update_detection_object(self, object_id):
        '''
        Asynchronous update for individual detection objects - only required once object
        updates are implemented
        '''
        pass

    async def process_viewports(self):
        if self.viewport_list == None or len(self.viewport_list) == 0:
            logger.error("Event loop initiated without drone viewports")
            return
        for vp in self.viewport_list:
            step_result = self.produce_viewport_result(vp)
            self.update_db(vp, step_result)
            self.send_result(vp, step_result)

    def produce_viewport_result(self, viewport):
        pass

    def update_db(self, viewport, returned_image):
        pass

    def send_result(self, viewport, returned_image):
        pass