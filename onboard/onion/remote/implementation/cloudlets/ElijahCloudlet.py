from interfaces import CloudletItf
import json
from json import JSONDecodeError
import threading
import time
import logging
import asyncio
import cv2

from cnc_protocol import cnc_pb2
from gabriel_protocol import gabriel_pb2
from gabriel_client.websocket_client import ProducerWrapper

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class ElijahCloudlet(CloudletItf.CloudletItf):

    def __init__(self):
        self.engine_results = {}
        self.source = 'command'
        self.model = 'coco'
        self.drone = None
        self.sample_rate = 1
        self.stop = True

    def processResults(self, result_wrapper):
        if len(result_wrapper.results) != 1:
            return

        for result in result_wrapper.results:
            if result.payload_type == gabriel_pb2.PayloadType.TEXT:
                payload = result.payload.decode('utf-8')
                data = ""
                try:
                    if len(payload) != 0:
                        data = json.loads(payload)
                        producer = result_wrapper.result_producer_name.value
                        self.engine_results[producer] = result
                except JSONDecodeError as e:
                    logger.error(f'Error decoding json: {payload}')
                except Exception as e:
                    print(e)
            else:
                logger.error(f"Got result type {result.payload_type}. Expected TEXT.")

    def startStreaming(self, drone, model, sample_rate):
        self.stop = False
        self.model = model
        self.drone = drone
        self.sample_rate = sample_rate

    def stopStreaming(self):
        self.stop = True

    def switchModel(self, model):
        self.model = model

    def produce_extras(self):
        extras = cnc_pb2.Extras()
        extras.drone_id = self.drone.getName()
        extras.location.latitude = self.drone.getLat()
        extras.location.longitude = self.drone.getLng()
        extras.detection_model = self.model
        return extras

    def sendFrame(self):
        async def producer():
            await asyncio.sleep(0.1)
            input_frame = gabriel_pb2.InputFrame()
            if not self.stop:
                try:
                    _, frame = cv2.imencode('.jpg', self.drone.getVideoFrame())
                    input_frame.payload_type = gabriel_pb2.PayloadType.IMAGE
                    input_frame.payloads.append(frame.tobytes())

                    extras = self.produce_extras()
                    if extras is not None:
                        input_frame.extras.Pack(extras)
                except Exception as e:
                    input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
                    input_frame.payloads.append("Unable to produce a frame!".encode('utf-8'))
                    logger.error(f'Unable to produce a frame: {e}')
            else:
                input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
                input_frame.payloads.append("Streaming not started, no frame to show.")

            return input_frame
                    
        return ProducerWrapper(producer=producer, source_name=self.source)

    def getResults(self, engine_key):
        try:    
            return self.engine_results.pop(engine_key)
        except:
            return None
