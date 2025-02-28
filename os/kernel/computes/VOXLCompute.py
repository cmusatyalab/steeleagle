import asyncio
import logging
import os
from enum import Enum

import cv2
import kernel.computes.onboard_compute_pb2 as onboard_compute_pb2
import numpy as np
import zmq
import zmq.asyncio
from cnc_protocol import cnc_pb2
from kernel.computes.ComputeItf import ComputeInterface
from kernel.DataStore import DataStore
from util.utils import SocketOperation, lazy_pirate_request, setup_socket

logger = logging.getLogger(__name__)

class ComputationType(Enum):
    OBJECT_DETECTION = 1
    DEPTH_ESTIMATION = 2

class VOXLCompute(ComputeInterface):
    '''
    Utilizes the onboard computational capabilities on the Modal AI VOXL 2.
    '''

    def __init__(self, compute_id: int, data_store: DataStore):
        super().__init__(compute_id)

        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.REQ)
        host = os.environ.get('LCE_HOST')
        port = os.environ.get('LCE_PORT')

        if host is None:
            logger.error("Host not specified")
            raise Exception("Host not specified")
        if port is None:
            logger.error("Port not specified")
            raise Exception("Port not specified")

        setup_socket(self.socket, SocketOperation.CONNECT, 'LCE_PORT',
                     'Created socket to connect to local compute engine',
                     host)
        self.server_endpoint = f'tcp://{host}:{port}'
        self.is_running = False
        self.frame_id = -1
        self.data_store = data_store

    async def run(self):
        self.is_running = True
        self.task = asyncio.create_task(self.run_loop())

    async def stop(self):
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass

    async def get_status(self):
        return super().get_status()

    async def set(self):
        raise NotImplemented()

    async def run_loop(self):
        '''
        Query data store in a loop and feed frames for processing to onboard
        compute engine.
        '''
        logger.info("VOXL compute is running")
        while self.is_running:
            frame_data = cnc_pb2.Frame()
            frame_id = self.data_store.get_raw_data(frame_data)

            # Wait for a new frame
            while frame_id is None or frame_id <= self.frame_id:
                await self.data_store.wait_for_new_data(type(frame_data))
                frame_id = self.data_store.get_raw_data(frame_data)
            self.frame_id = frame_id

            if frame_data.data != b'':
                logger.info(f"VOXL compute got new frame {frame_data.id} from data store")
                frame_bytes = frame_data.data
                nparr = np.frombuffer(frame_bytes, dtype = np.uint8)

                height = frame_data.height
                width = frame_data.width
                channels = frame_data.channels

                frame = nparr.reshape(height, width, channels)

                await self.process_frame(frame, ComputationType.OBJECT_DETECTION)

    async def process_frame(self, frame: np.ndarray, computation_type: ComputationType):
        '''
        Send frames to onboard compute engine for processing. Currently
        only supports object detection, and prints detected classes.
        '''
        request = onboard_compute_pb2.ComputeRequest()
        request.frame_data = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_YUYV).tobytes()
        request.frame_width = frame.shape[1]
        request.frame_height = frame.shape[0]

        if computation_type != ComputationType.OBJECT_DETECTION:
            raise Exception("Computation type not supported")

        frame_width = request.frame_width
        frame_height = request.frame_height
        logger.info(f"Sending work item to local compute engine; {frame_width=} {frame_height=}")

        reply = None
        (self.socket, reply) = await lazy_pirate_request(
            self.socket, request.SerializeToString(), self.context,
            self.server_endpoint)

        if reply == None:
            logger.error(f"Local compute engine did not respond to request")
            return

        logger.info(f"Received response from local compute engine")
        detections = onboard_compute_pb2.ComputeResult()
        detections.ParseFromString(reply)
        logger.info(f"Received detections: {detections}")

