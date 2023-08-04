from interfaces import CloudletItf
import json
import threading
import time
import logging
import asyncio

from cnc_protocol import cnc_pb2
from gabriel_protocol import gabriel_pb2
from gabriel_client.websocket_client import ProducerWrapper

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class ElijahCloudlet(CloudletItf.CloudletItf):

    def __init__(self):
        self.engine_results = {}
        self.comm = comm
        self.source = 'openscout'
        self.model = 'coco'
        self.drone = None

    def processResults(self, result_wrapper):
        if len(result_wrapper.results) != 1:
            logger.error('Got %d results from server'.
                    len(result_wrapper.results))
            return

        for result in result_wrapper.results:
            if result.payload_type == gabriel_pb2.PayloadType.TEXT:
                payload = result.payload.decode('utf-8')
                try:
                    data = json.loads(payload)
                    producer = result_wrapper.producer
                    self.engine_results[producer] = result
                except Exception as e:
                    logger.error(f'Error decoding json {data}')
            else:
                logger.error(f"Got result type {result.payload_type}. Expected TEXT.")

    def startStreaming(self, drone, model, sample_rate):
        self.stop = False
        self.model = model
        self.drone = drone
        def stream(self, sample_rate):
            while not self.stop:
                self.sendFrame(self.drone.getVideoFrame())
                time.sleep(1 / sample_rate)

        self.stream = threading.Thread(target=stream, args=(self, sample_rate, ))
        self.stream.start()

    def stopStreaming(self):
        self.stop = True
        self.stream.join()

    def produce_extras(self):
        extras = cnc_pb2.Extras()
        extras.drone_id = self.drone.getName()
        extras.location.latitude = self.drone.getLat()
        extras.location.longitude = self.drone.getLng()
        extras.detection_model = self.model
        return extras

    def sendFrame(self, frame):
        if frame is None:
            return
        async def producer():
            await asyncio.sleep(0.3)
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.IMAGE
            input_frame.payloads.append(frame.tobytes())

            extras = self.produce_extras()
            if extras is not None:
                input_frame.extras.Pack(extras)
            return input_frame

        return [
            ProducerWrapper(producer=producer, source_name=self.source)
        ]

    def getResults(self, engine_key):
        try:    
            return self.engine_results.pop(engine_key)
        except:
            return None
