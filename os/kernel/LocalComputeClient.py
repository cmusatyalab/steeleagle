import asyncio
import cv2
from enum import Enum
import logging
import numpy as np
import onboard_compute_pb2
import sys
from util.utils import setup_socket
import zmq
import zmq.asyncio

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)

class ComputationType(Enum):
    OBJECT_DETECT = 1

class LocalComputeClient:
    def __init__(self):
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.REQ)
        setup_socket(self.socket, 'connect', 'LCE_PORT', 'Created socket to connect to local compute engine', 'localhost')

    async def process_frame(self, frame, computation_type):
        request = onboard_compute_pb2.ComputeRequest()
        request.frame_data = frame
        request.frame_width = 1280
        request.frame_height = 720

        if computation_type != ComputationType.OBJECT_DETECT:
            raise Exception("Computation type not supported")

        logger.info("Sending work item to local compute engine")
        await self.socket.send(request.SerializeToString())

        result = await self.socket.recv()
        logger.info(f"Received response {result} from local compute engine")

async def main():
    logger.info("Starting local compute client")
    client = LocalComputeClient()
    robomaster_img = cv2.imread("robomaster.jpg")
    image_yuv = cv2.cvtColor(robomaster_img, cv2.COLOR_BGR2YUV_Y422)

    frame = image_yuv.tobytes()

    # with open('robomaster_yuv422.yuv', 'wb') as f:
    #     f.write(frame)

    result = await client.process_frame(frame, ComputationType.OBJECT_DETECT)

if __name__ == "__main__":
    asyncio.run(main())
