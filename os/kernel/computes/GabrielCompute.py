import asyncio
import json
import logging
import os
import time
import cv2
import numpy as np
from gabriel_protocol import gabriel_pb2
from gabriel_client.zeromq_client import ProducerWrapper, ZeroMQClient
from util.timer import Timer
from cnc_protocol import cnc_pb2
from kernel.computes.ComputeItf import ComputeInterface
from kernel.DataStore import DataStore

logger = logging.getLogger(__name__)


class GabrielCompute(ComputeInterface):
    def __init__(self, compute_id, data_store:DataStore):
        super().__init__(compute_id)
        
        # remote computation parameters
        self.set_params = {
            "model": "coco",
            "hsv_lower": None,
            "hsv_upper": None
        }
        
        # Gabriel
        gabriel_server = os.environ.get('STEELEAGLE_GABRIEL_SERVER')
        logger.info(f'Gabriel compute: Gabriel server: {gabriel_server}')
        gabriel_port = os.environ.get('STEELEAGLE_GABRIEL_PORT')
        logger.info(f'Gabriel compute: Gabriel port: {gabriel_port}')
        self.gabriel_server = gabriel_server
        self.gabriel_port = gabriel_port
        self.engine_results = {}
        self.drone_registered = False
        self.gabriel_client = ZeroMQClient(
            self.gabriel_server, self.gabriel_port,
            [self.get_telemetry_producer(), self.get_frame_producer()], self.processResults
        )
        
        # data_store
        self.data_store = data_store
    
    async def run(self):
        await self.gabriel_client.launch_async()
        
    
    def set(self):
        self.set_params["model"] = None
        self.set_params["hsv_lower"] = None
        self.set_params["hsv_upper"] = None
        
       
    def stop(self):
        """Stopping the worker."""
        pass
    
    def getStatus(self):
        """Getting the status of the worker."""
        return self.compute_status
    
    ######################################################## GABRIEL COMPUTE ############################################################    
    def processResults(self, result_wrapper):
        if len(result_wrapper.results) != 1:
            return

        for result in result_wrapper.results:
            if result.payload_type == gabriel_pb2.PayloadType.TEXT:
                payload = result.payload.decode('utf-8')
                try:
                    if len(payload) != 0:
                        # get engine id
                        compute_type = result_wrapper.result_producer_name.value
                        # get timestamp
                        timestamp = time.time()
                        # update
                        logger.debug(f"Gabriel compute: timestamp = {timestamp}, compute type = {compute_type}, result = {result}")
                        self.data_store.update_compute_result(self.compute_id, compute_type, payload, timestamp)   
                except Exception as e:
                    logger.error(f"Gabriel compute processResults: error processing result: {e}")
            else:
                logger.debug(f"Got result type {result.payload_type}. Expected TEXT.")
                
    def get_frame_producer(self):
        async def producer():
            await asyncio.sleep(0)
            self.compute_status = self.ComputeStatus.Connected

            logger.debug(f"Frame producer: starting converting {time.time()}")
            input_frame = gabriel_pb2.InputFrame()
            frame_data = cnc_pb2.Frame()
            self.data_store.get_raw_data(frame_data)
            tel_data = cnc_pb2.Telemetry()
            self.data_store.get_raw_data(tel_data)
            try:
                if frame_data is not None and frame_data.data != b'' and tel_data is not None:
                    logger.debug("Waiting for new frame from driver")
                    logger.info(f"New frame frame_id={frame_data.id} available from driver, tel_data={tel_data}")

                    frame_bytes = frame_data.data

                    nparr = np.frombuffer(frame_bytes, dtype = np.uint8)
                    frame = cv2.imencode('.jpg', nparr.reshape(frame_data.height, frame_data.width, frame_data.channels))[1]
                    input_frame.payload_type = gabriel_pb2.PayloadType.IMAGE
                    input_frame.payloads.append(frame.tobytes())

                    # produce extras
                    extras = cnc_pb2.Extras()
                    extras.drone_id = tel_data.drone_name
                    extras.location.latitude = tel_data.global_position.latitude
                    extras.location.longitude = tel_data.global_position.longitude
                    
                    if self.set_params['model'] is not None:
                        extras.detection_model = self.set_params['model']
                    if self.set_params['hsv_lower'] is not None:
                        extras.lower_bound.H = self.set_params['hsv_lower'][0]
                        extras.lower_bound.S = self.set_params['hsv_lower'][1]
                        extras.lower_bound.V = self.set_params['hsv_lower'][2]
                    if self.set_params['hsv_upper'] is not None:
                        extras.upper_bound.H = self.set_params['hsv_upper'][0]
                        extras.upper_bound.S = self.set_params['hsv_upper'][1]
                        extras.upper_bound.V = self.set_params['hsv_upper'][2]
                    if extras is not None:
                        input_frame.extras.Pack(extras)
                else:
                    logger.info('Gabriel compute Frame producer: frame is None')
                    input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
                    input_frame.payloads.append("Streaming not started, no frame to show.".encode('utf-8'))
            except Exception as e:
                input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
                input_frame.payloads.append("Unable to produce a frame!".encode('utf-8'))
                logger.error(f'Gabriel compute Frame producer: unable to produce a frame: {e}')

            logger.debug(f"Gabriel compute Frame producer: finished time {time.time()}")
            return input_frame
        return ProducerWrapper(producer=producer, source_name='telemetry')

    def get_telemetry_producer(self):
        async def producer():
            await asyncio.sleep(0)
            
            self.compute_status = self.ComputeStatus.Connected
            logger.debug(f"tel producer: starting time {time.time()}")
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
            input_frame.payloads.append('heartbeart'.encode('utf8'))
            tel_data = cnc_pb2.Telemetry()
            self.data_store.get_raw_data(tel_data)
            try:
                if tel_data is not None:
                    logger.debug("Gabriel compute telemetry producer: sending telemetry")

                    extras = cnc_pb2.Extras()
                    extras.drone_id = tel_data.drone_name
                    extras.location.latitude = tel_data.global_position.latitude
                    extras.location.longitude = tel_data.global_position.longitude
                    extras.location.altitude = tel_data.global_position.altitude
                    extras.status.battery = tel_data.battery
                    extras.status.mag = tel_data.mag
                    # arbitrary values for now
                    extras.status.bearing = 0
                    extras.status.rssi = 0

                    # Register when we start sending telemetry
                    if not self.drone_registered:
                        logger.info("Gabriel compute telemetry producer: Sending registeration request to backend")
                        extras.registering = True
                        self.drone_registered = True
                        
                    logger.debug('Gabriel compute telemetry producer: sending Gabriel telemerty! content: {}'.format(extras))
                    input_frame.extras.Pack(extras)
                else:
                    logger.error('Telemetry unavailable')
            except Exception as e:
                logger.debug(f'Gabriel compute telemetry producer: {e}')
            logger.debug(f"tel producer: finished time {time.time()}")
            return input_frame

        return ProducerWrapper(producer=producer, source_name='telemetry')
