import asyncio
import cv2
from enum import Enum
import logging
import numpy as np
import os
import onboard_compute_pb2
import sys
from util.utils import setup_socket, SocketOperation, lazy_pirate_request
import zmq
import zmq.asyncio

logger = logging.getLogger(__name__)

class ComputationType(Enum):
    OBJECT_DETECTION = 1
    DEPTH_ESTIMATION = 2

class LocalComputeClient:
    def __init__(self, frame_width, frame_height):
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.REQ)
        host = os.environ.get('LCE_HOST')
        port = os.environ.get('LCE_PORT')

        setup_socket(self.socket, SocketOperation.CONNECT, 'LCE_PORT',
                     'Created socket to connect to local compute engine',
                     host)
        self.server_endpoint = f'tcp://{host}:{port}'
        self.frame_width = frame_width
        self.frame_height = frame_height

    async def process_frame(self, frame, computation_type):
        request = onboard_compute_pb2.ComputeRequest()
        request.frame_data = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV_YUYV).tobytes()
        request.frame_width = self.frame_width
        request.frame_height = self.frame_height

        if computation_type != ComputationType.OBJECT_DETECTION:
            raise Exception("Computation type not supported")

        logger.info("Sending work item to local compute engine")

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
        print(detections)

async def main():
    logger.info("Starting local compute client")
    client = LocalComputeClient(1280, 720)
    robomaster_img = cv2.imread("jingao.jpg")
    image_yuv = cv2.cvtColor(robomaster_img, cv2.COLOR_BGR2YUV_YUYV)

    frame = image_yuv.tobytes()

    # with open('robomaster_yuv422.yuv', 'wb') as f:
    #     f.write(frame)

    result = await client.process_frame(frame, ComputationType.OBJECT_DETECTION)

if __name__ == "__main__":
    asyncio.run(main())
