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
from datasinks.ComputeItf import ComputeInterface
from hub.data_store import DataStore
from protocol import dataplane_pb2 as data_protocol
from protocol import controlplane_pb2 as control_protocol
from protocol import common_pb2 as common_protocol

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
            [self.get_telemetry_producer(), self.get_frame_producer()], self.process_results
        )

        # data_store
        self.data_store = data_store
        self.frame_id = -1

    async def run(self):
        logger.info(f"Gabriel compute: launching Gabriel client")
        await self.gabriel_client.launch_async()
        

    def set(self):
        self.set_params["model"] = None
        self.set_params["hsv_lower"] = None
        self.set_params["hsv_upper"] = None


    def stop(self):
        """Stopping the worker."""
        pass

    def get_status(self):
        """Getting the status of the worker."""
        return self.compute_status

    ######################################################## GABRIEL COMPUTE ############################################################
    def process_results(self, result_wrapper):
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
                    logger.error(f"Gabriel compute process_results: error processing result: {e}")
            else:
                logger.debug(f"Got result type {result.payload_type}. Expected TEXT.")

    def get_frame_producer(self):
        async def producer():
            await asyncio.sleep(0.1)
            self.compute_status = self.ComputeStatus.Connected

            logger.debug(f"Frame producer: starting converting {time.time()}")
            input_frame = gabriel_pb2.InputFrame()
            frame_data = data_protocol.Frame()

            frame_id = self.data_store.get_raw_data(frame_data)

            # Wait for a new frame
            while frame_id is None or frame_id <= self.frame_id:
                await self.data_store.wait_for_new_data(type(frame_data))
                logger.info("Waiting for new frame from driver")
                frame_id = self.data_store.get_raw_data(frame_data)
            self.frame_id = frame_id

            tel_data = data_protocol.Telemetry()
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
                    compute_command = control_protocol.Request()
                    compute_command.cpt.key = self.compute_id

                    if self.set_params['model'] is not None:
                        compute_command.cpt.model = self.set_params['model']
                    if self.set_params['hsv_lower'] is not None:
                        compute_command.cpt.lower_bound - self.set_params['hsv_lower'][0]
                        compute_command.cpt.lower_bound - self.set_params['hsv_lower'][1]
                        compute_command.cpt.lower_bound - self.set_params['hsv_lower'][2]
                    if self.set_params['hsv_upper'] is not None:
                        compute_command.cpt.upper_bound - self.set_params['hsv_upper'][0]
                        compute_command.cpt.upper_bound - self.set_params['hsv_upper'][1]
                        compute_command.cpt.upper_bound - self.set_params['hsv_upper'][2]
                    if compute_command is not None:
                        input_frame.extras.Pack(compute_command)
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
            await asyncio.sleep(0.1)

            self.compute_status = self.ComputeStatus.Connected
            logger.debug(f"tel producer: starting time {time.time()}")
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
            input_frame.payloads.append('heartbeart'.encode('utf8'))
            tel_data = data_protocol.Telemetry()
            self.data_store.get_raw_data(tel_data)
            try:
                if tel_data is not None:
                    logger.debug("Gabriel compute telemetry producer: sending telemetry")
                    # Register when we start sending telemetry
                    if not self.drone_registered:
                        logger.info("Gabriel compute telemetry producer: Sending registeration request to backend")
                        tel_data.uptime = 0
                        self.drone_registered = True
                    logger.debug('Gabriel compute telemetry producer: sending Gabriel telemerty! content: {}'.format(tel_data))
                    input_frame.extras.Pack(tel_data)
                else:
                    logger.error('Telemetry unavailable')
            except Exception as e:
                logger.debug(f'Gabriel compute telemetry producer: {e}')
            logger.debug(f"tel producer: finished time {time.time()}")
            return input_frame

        return ProducerWrapper(producer=producer, source_name='telemetry')
