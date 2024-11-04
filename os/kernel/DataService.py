import time
import cv2
import numpy as np
import zmq
import zmq.asyncio
import asyncio
import os
import sys
import logging
import json
from util.utils import setup_socket, SocketOperation
from util.timer import Timer
from cnc_protocol import cnc_pb2
from gabriel_protocol import gabriel_pb2
from gabriel_client.zeromq_client import ProducerWrapper, ZeroMQClient
from kernel.Service import Service
from LocalComputeClient import LocalComputeClient, ComputationType

logging_format = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
logging.basicConfig(level=os.environ.get('LOG_LEVEL', logging.INFO),
                    format=logging_format)
logger = logging.getLogger(__name__)

if os.environ.get("LOG_TO_FILE") == "true":
    file_handler = logging.FileHandler('data_service.log')
    file_handler.setFormatter(logging.Formatter(logging_format))
    logger.addHandler(file_handler)

class DataService(Service):
    def __init__(self, gabriel_server, gabriel_port):
        super().__init__()

        # setting up args
        self.telemetry_cache = {
            "connection": None,
            "drone_name": None,
            "location": {
                "latitude": None,
                "longitude": None,
                "altitude": None
            },
            "battery": None,
            "magnetometer": None,
            "bearing": None
        }
        self.telemetry_updated = asyncio.Event()
        self.frame_cache = {
            "data": None,
            "height": None,
            "width": None,
            "channels": None,
            "id": None
        }
        self.frame_updated = asyncio.Event()
        self.result_cache = {}
        # Gabriel
        self.gabriel_server = gabriel_server
        self.gabriel_port = gabriel_port
        self.engine_results = {}
        self.drone_registered = False
        self.gabriel_client = ZeroMQClient(
            self.gabriel_server, self.gabriel_port,
            [self.get_telemetry_producer(), self.get_frame_producer()], self.processResults
        )
        # remote computation parameters
        self.params = {
            "model": None,
            "hsv_lower": None,
            "hsv_upper": None
        }

        # Result Cache

        # Setting up conetxt
        context = zmq.asyncio.Context()

        # Setting up sockets
        tel_sock = context.socket(zmq.SUB)
        cam_sock = context.socket(zmq.SUB)
        cpt_sock = context.socket(zmq.REP)
        tel_sock.setsockopt(zmq.SUBSCRIBE, b'') # Subscribe to all topics
        tel_sock.setsockopt(zmq.CONFLATE, 1)
        cam_sock.setsockopt(zmq.SUBSCRIBE, b'')  # Subscribe to all topics
        cam_sock.setsockopt(zmq.CONFLATE, 1)
        self.cam_sock = cam_sock
        self.tel_sock = tel_sock
        self.cpt_sock = cpt_sock
        setup_socket(tel_sock, SocketOperation.BIND, 'TEL_PORT', 'Created telemetry socket endpoint')
        setup_socket(cam_sock, SocketOperation.BIND, 'CAM_PORT', 'Created camera socket endpoint')

        self.local_compute_client = LocalComputeClient(1280, 720)

        # setting up tasks
        tel_task = asyncio.create_task(self.telemetry_handler())
        cam_task = asyncio.create_task(self.camera_handler())
        gab_task = asyncio.create_task(self.gabriel_client.launch_async())
        local_compute_task = asyncio.create_task(self.local_compute_task())

        # registering context, sockets and tasks to service
        self.register_context(context)
        self.register_socket(tel_sock)
        self.register_socket(cam_sock)
        self.register_socket(cpt_sock)
        self.register_task(tel_task)
        self.register_task(cam_task)
        self.register_task(gab_task)
        self.register_task(local_compute_task)

    ######################################################## DRIVER ############################################################
    async def telemetry_handler(self):
        logger.info('Telemetry handler started')
        while True:
            try:
                logger.debug(f"Telemetry handler: started time {time.time()}")
                msg = await self.tel_sock.recv()
                telemetry = cnc_pb2.Telemetry()
                telemetry.ParseFromString(msg)

                # self.telemetry_cache['connection'] = telemetry.connection_status.is_connected
                self.telemetry_cache['drone_name'] = telemetry.drone_name
                self.telemetry_cache['location']['latitude'] = telemetry.global_position.latitude
                self.telemetry_cache['location']['longitude'] = telemetry.global_position.longitude
                self.telemetry_cache['location']['altitude'] = telemetry.global_position.altitude
                self.telemetry_cache['battery'] = telemetry.battery
                self.telemetry_cache['magnetometer'] = telemetry.mag
                self.telemetry_cache['bearing'] = telemetry.drone_attitude.yaw

                logger.debug(f"Telemetry handler: finished time {time.time()}")
                self.telemetry_updated.set()
            except Exception as e:
                logger.error(f"Telemetry handler: {e}")

    async def camera_handler(self):
        logger.info('Camera handler started')
        while True:
            try:
                logger.debug(f"Camera handler: started time {time.time()}")

                msg = await self.cam_sock.recv()
                frame = cnc_pb2.Frame()
                frame.ParseFromString(msg)

                self.frame_cache['data'] = frame.data
                self.frame_cache['height'] = frame.height
                self.frame_cache['width'] = frame.width
                self.frame_cache['channels'] = frame.channels
                self.frame_cache['id'] = frame.id

                logger.debug(f'Camera handler: received frame frame_id={self.frame_cache["id"]}')
                logger.debug(f"Camera handler: finished time {time.time()}")

                self.frame_updated.set()
            except Exception as e:
                logger.error(f"Camera handler: {e}")

    async def compute_handler(self):
        logger.info('Compute handler started')
        while True:
            try:
                msg = await self.cpt_sock.recv()
                req = cnc_pb2.ComputeRequest()
                req.ParseFromString(msg)

                if req.engineKey in self.result_cache.keys():
                    resp = ComputeResult()
                    resp.result = self.result_cache[req.engineKey]
                    if req.invalidateCache:
                        self.result_cache.pop(req.engineKey, None)
                    self.cpt_sock.send(resp.SerializeToString())
            except Exception as e:
                pass

    ######################################################## REMOTE COMPUTE ############################################################
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
                        self.result_cache[producer] = result
                        logger.debug(f'Got new result for producer {producer}: {result}')
                except json.JSONDecodeError as e:
                    logger.debug(f'Error decoding json: {payload}')
                except Exception as e:
                    print(e)
            else:
                logger.debug(f"Got result type {result.payload_type}. Expected TEXT.")

    def get_frame_producer(self):
        async def producer():
            await asyncio.sleep(0)

            logger.debug(f"Frame producer: starting converting {time.time()}")
            input_frame = gabriel_pb2.InputFrame()
            if self.frame_cache['data'] is not None and self.telemetry_cache['drone_name'] is not None:
                try:
                    logger.debug("Waiting for new frame from driver")
                    await self.frame_updated.wait()
                    logger.debug("New frame available from driver")

                    frame_bytes = self.frame_cache['data']
                    nparr = np.frombuffer(frame_bytes, dtype = np.uint8)
                    with Timer(logger, "Encoding frame to jpg"):
                        frame = cv2.imencode('.jpg', nparr.reshape(self.frame_cache['height'], self.frame_cache['width'], self.frame_cache['channels']))[1]

                    input_frame.payload_type = gabriel_pb2.PayloadType.IMAGE
                    input_frame.payloads.append(frame.tobytes())

                    # produce extras
                    extras = cnc_pb2.Extras()
                    extras.drone_id = self.telemetry_cache['drone_name']
                    extras.location.latitude = self.telemetry_cache['location']['latitude']
                    extras.location.longitude = self.telemetry_cache['location']['longitude']
                    if self.params['model'] is not None:
                        extras.detection_model = self.params['model']
                    if self.params['hsv_lower'] is not None:
                        extras.lower_bound.H = self.params['hsv_lower'][0]
                        extras.lower_bound.S = self.params['hsv_lower'][1]
                        extras.lower_bound.V = self.params['hsv_lower'][2]
                    if self.params['hsv_upper'] is not None:
                        extras.upper_bound.H = self.params['hsv_upper'][0]
                        extras.upper_bound.S = self.params['hsv_upper'][1]
                        extras.upper_bound.V = self.params['hsv_upper'][2]
                    if extras is not None:
                        input_frame.extras.Pack(extras)

                except Exception as e:
                    input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
                    input_frame.payloads.append("Unable to produce a frame!".encode('utf-8'))
                    logger.error(f'Frame producer: unable to produce a frame: {e}')
            else:
                logger.debug('Frame producer: frame is None')
                input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
                input_frame.payloads.append("Streaming not started, no frame to show.".encode('utf-8'))

            logger.debug(f"Frame producer: finished time {time.time()}")
            self.frame_updated.clear()
            return input_frame

        return ProducerWrapper(producer=producer, source_name='telemetry')

    def get_telemetry_producer(self):
        async def producer():
            await asyncio.sleep(0)

            logger.debug(f"tel producer: starting time {time.time()}")
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
            input_frame.payloads.append('heartbeart'.encode('utf8'))

            extras = cnc_pb2.Extras()

            try:
                if self.telemetry_cache['drone_name'] is None:
                    logger.info('Telemetry unavailable')
                else:
                    logger.debug("Waiting for new telemetry from driver")
                    await self.telemetry_updated.wait()
                    logger.debug("New telemetry available from driver")

                    # Proceed with normal assignments
                    extras.drone_id = self.telemetry_cache['drone_name']
                    extras.location.latitude = self.telemetry_cache['location']['latitude']
                    extras.location.longitude = self.telemetry_cache['location']['longitude']
                    extras.location.altitude = self.telemetry_cache['location']['altitude']

                    extras.status.battery = self.telemetry_cache['battery']
                    extras.status.mag = self.telemetry_cache['magnetometer']
                    extras.status.bearing = self.telemetry_cache['bearing']
                    extras.status.rssi = 0

                    # Register when we start sending telemetry
                    if not self.drone_registered:
                        logger.info("Sending registeration request to backend")
                        extras.registering = True
                        self.drone_registered = True

                    logger.debug(f'Gabriel client telemetry producer: {extras}')
            except Exception as e:
                logger.debug(f'Gabriel client telemetry producer: {e}')

            logger.debug('Gabriel client telemetry producer: sending Gabriel frame!')
            input_frame.extras.Pack(extras)

            logger.debug(f"tel producer: finished time {time.time()}")

            self.telemetry_updated.clear()
            return input_frame

        return ProducerWrapper(producer=producer, source_name='telemetry')

    async def local_compute_task(self):
        logger.info('Local compute task started')
        frame_id = None
        while True:
            await asyncio.sleep(0)
            if self.frame_cache['data'] is not None and (frame_id is None or self.frame_cache['id'] > frame_id):
                frame_bytes = self.frame_cache['data']
                nparr = np.frombuffer(frame_bytes, dtype = np.uint8)

                height = self.frame_cache['height']
                width = self.frame_cache['width']
                channels = self.frame_cache['channels']
                frame = nparr.reshape(height, width, channels)
                logger.info("Sending frame to local compute client")
                frame_id = self.frame_cache['id']
                try:
                    await self.local_compute_client.process_frame(frame, ComputationType.OBJECT_DETECTION)
                except Exception as e:
                    logger.error(f"Error processing local compute request: {e}")

######################################################## MAIN ##############################################################
async def async_main():
    logger.info("Main: starting DataService")
    gabriel_server = os.environ.get('STEELEAGLE_GABRIEL_SERVER')
    logger.info(f'Main: Gabriel server: {gabriel_server}')
    gabriel_port = os.environ.get('STEELEAGLE_GABRIEL_PORT')
    logger.info(f'Main: Gabriel port: {gabriel_port}')

    # init DataService
    data_service = DataService(gabriel_server, gabriel_port)

    # run DataService
    await data_service.start()

if __name__ == "__main__":
    asyncio.run(async_main())
