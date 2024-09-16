import time
import cv2
import numpy as np
import zmq
import zmq.asyncio
import asyncio
import os
import sys
import logging
from util.utils import setup_socket
from cnc_protocol import cnc_pb2
from gabriel_protocol import gabriel_pb2
from gabriel_client.zeromq_client import ProducerWrapper, ZeroMQClient
from kernel.Service import Service

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)



class RemoteComputeService(Service):
    def __init__(self, gabriel_server, gabriel_port):
        super().__init__()
        
        # setting up args
        self.telemetry_cache = {
            "location": {
                "latitude": None,
                "longitude": None,
                "altitude": None
            },
            "battery": None,
            "magnetometer": None,
            "bearing": None
        }
        self.frame_cache = {
            "data": None,
            "height": None,
            "width": None,
            "channels": None,
            "id": None
        }
        # Gabriel
        self.gabriel_server = gabriel_server
        self.gabriel_port = gabriel_port
        self.engine_results = {}
        self.gabriel_client_heartbeats = 0
        self.gabriel_client = ZeroMQClient(
            self.gabriel_server, self.gabriel_port,
            [self.get_telemetry_producer(), self.get_frame_producer()], self.processResults
        )
        # user defined parameters
        self.model = 'coco'
        self.hsv_upper = [50,255,255]
        self.hsv_lower = [30,100,100]
        # drone id
        self.drone_id = "ant"
        
        # Setting up conetxt
        context = zmq.asyncio.Context()
        
        # Setting up sockets
        tel_sock = context.socket(zmq.SUB)
        cam_sock = context.socket(zmq.SUB)
        tel_sock.setsockopt(zmq.SUBSCRIBE, b'') # Subscribe to all topics
        tel_sock.setsockopt(zmq.CONFLATE, 1)
        cam_sock.setsockopt(zmq.SUBSCRIBE, b'')  # Subscribe to all topics
        cam_sock.setsockopt(zmq.CONFLATE, 1)
        self.cam_sock = cam_sock
        self.tel_sock = tel_sock
        setup_socket(tel_sock, 'bind', 'TEL_PORT', 'Created telemetry socket endpoint')
        setup_socket(cam_sock, 'bind', 'CAM_PORT', 'Created camera socket endpoint')
        
        # setting up tasks
        tel_task = asyncio.create_task(self.telemetry_handler())
        cam_task = asyncio.create_task(self.camera_handler())
        gab_task = asyncio.create_task(self.gabriel_client.launch_async())
        
        # registering context, sockets and tasks to service
        self.register_context(context)
        self.register_socket(tel_sock)
        self.register_socket(cam_sock)
        self.register_task(tel_task)
        self.register_task(cam_task)
        self.register_task(gab_task)
    
    ######################################################## DRIVER ############################################################  
    async def telemetry_handler(self):
        logger.info('Telemetry handler started')
        while True:
            try:
                logger.debug(f"telemetry_handler: started time {time.time()}")
                msg = await self.tel_sock.recv()
                telemetry = cnc_pb2.Telemetry()
                telemetry.ParseFromString(msg)
                self.telemetry_cache['location']['latitude'] = telemetry.global_position.latitude
                self.telemetry_cache['location']['longitude'] = telemetry.global_position.longitude
                self.telemetry_cache['location']['altitude'] = telemetry.global_position.altitude
                self.telemetry_cache['battery'] = telemetry.battery
                self.telemetry_cache['magnetometer'] = telemetry.mag
                self.telemetry_cache['bearing'] = telemetry.drone_attitude.yaw
                logger.debug(f'Telemetry Data: {self.telemetry_cache}')
                logger.debug(f"telemetry_handler: finished time {time.time()}")
            except Exception as e:
                logger.error(f"Telemetry Handler: {e}")
    
    async def camera_handler(self):
        logger.info('Camera handler started')
        while True:
            try:
                logger.debug(f"Camera Handler: started time {time.time()}")
                msg = await self.cam_sock.recv()
                frame = cnc_pb2.Frame()
                frame.ParseFromString(msg)
                self.frame_cache['data'] = frame.data
                self.frame_cache['height'] = frame.height
                self.frame_cache['width'] = frame.width
                self.frame_cache['channels'] = frame.channels
                self.frame_cache['id'] = frame.id
                logger.debug(f'Camera Frame ID: {self.frame_cache["id"]}')
                logger.debug(f"Camera Handler: finished time {time.time()}")
            except Exception as e:
                logger.error(f"Camera Handler: {e}")
    
    ######################################################## REMOTE COMPUTE ############################################################           
    def processResults(self, result_wrapper):
        pass

    def get_frame_producer(self):
        async def producer():
            await asyncio.sleep(0)
            
            logger.debug(f"Frame Producer: starting converting {time.time()}")
            input_frame = gabriel_pb2.InputFrame()
            if self.frame_cache['data'] is not None:
                try:
                    frame_bytes = self.frame_cache['data']
                    nparr = np.frombuffer(frame_bytes, dtype = np.uint8)
                    frame = cv2.imencode('.jpg', nparr.reshape(self.frame_cache['height'], self.frame_cache['width'], self.frame_cache['channels']))[1]
                    
                    input_frame.payload_type = gabriel_pb2.PayloadType.IMAGE
                    input_frame.payloads.append(frame.tobytes())
                    
                    # produce extras
                    extras = cnc_pb2.Extras()
                    extras.drone_id = self.drone_id
                    extras.location.latitude = self.telemetry_cache['location']['latitude']
                    extras.location.longitude = self.telemetry_cache['location']['longitude']
                    extras.detection_model = self.model
                    extras.lower_bound.H = self.hsv_lower[0]
                    extras.lower_bound.S = self.hsv_lower[1]
                    extras.lower_bound.V = self.hsv_lower[2]
                    extras.upper_bound.H = self.hsv_upper[0]
                    extras.upper_bound.S = self.hsv_upper[1]
                    extras.upper_bound.V = self.hsv_upper[2]
                    if extras is not None:
                        input_frame.extras.Pack(extras)

                except Exception as e:
                    input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
                    input_frame.payloads.append("Unable to produce a frame!".encode('utf-8'))
                    logger.error(f'frame_producer: Unable to produce a frame: {e}')
            else:
                logger.debug('Frame producer: Frame is None')
                input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
                input_frame.payloads.append("Streaming not started, no frame to show.".encode('utf-8'))
                
            logger.debug(f"Frame Producer: finished time {time.time()}")
            return input_frame

        return ProducerWrapper(producer=producer, source_name='telemetry')
    
    def get_telemetry_producer(self):
        async def producer():
            await asyncio.sleep(0)
            
            logger.debug(f"tel Producer: starting time {time.time()}")
            self.gabriel_client_heartbeats += 1
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
            input_frame.payloads.append('heartbeart'.encode('utf8'))

            extras = cnc_pb2.Extras()
            # test
            extras.drone_id = self.drone_id
            extras.status.rssi = 0
            
            try:
                if all(value is None for value in self.telemetry_cache.values()):
                    logger.info('All telemetry_cache values are None')
                else:
                    # Proceed with normal assignments
                    extras.location.latitude = self.telemetry_cache['location']['latitude']
                    extras.location.longitude = self.telemetry_cache['location']['longitude']
                    extras.location.altitude = self.telemetry_cache['location']['altitude']

                    extras.status.battery = self.telemetry_cache['battery']    
                    extras.status.mag = self.telemetry_cache['magnetometer']
                    extras.status.bearing = self.telemetry_cache['bearing']
                    
                    logger.debug(f'Gabriel Client Telemetry Producer: {extras}')
                
                # result = await self.send_driver_command(ManualCommand.CONNECTION, None)
                # if self.drone_type == DroneType.VESPER:
                #     extras.status.rssi = result.connectionStatus.radio_rssi
                # elif self.drone_type == DroneType.PARROT:
                #     extras.status.rssi = result.connectionStatus.wifi_rssi
                # elif self.drone_type == DroneType.VXOL:
                #     extras.status.rssi = result.connectionStatus.wifi_rssi
                # else:
                #     extras.status.rssi = result.connectionStatus.cellular_rssi
                
                
            except Exception as e:
                logger.debug(f'Gabriel Client Telemetry Producer: {e}')

            # Register on the first frame
            if self.gabriel_client_heartbeats == 1:
                extras.registering = True

            logger.debug('Gabriel Client Telemetry Producer: sending Gabriel frame!')
            input_frame.extras.Pack(extras)
            
            logger.debug(f"tel Producer: finished time {time.time()}")
            return input_frame

        return ProducerWrapper(producer=producer, source_name='telemetry')
    
######################################################## MAIN ##############################################################             
async def async_main():
    logger.info("Main: starting RemoteComputeService")
    gabriel_server = os.environ.get('STEELEAGLE_GABRIEL_SERVER')
    logger.info(f'Main: Gabriel server: {gabriel_server}')
    gabriel_port = os.environ.get('STEELEAGLE_GABRIEL_PORT')
    logger.info(f'Main: Gabriel port: {gabriel_port}')

    # init RemoteComputeService
    rc_service = RemoteComputeService(gabriel_server, gabriel_port)
    
    # run RemoteComputeService
    await rc_service.start()
                 
        
    
if __name__ == "__main__":

    asyncio.run(async_main())
