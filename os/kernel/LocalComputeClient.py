import asyncio
from enum import Enum
from gabriel_protocol import gabriel_pb2
import logging
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
        if not isinstance(frame, gabriel_pb2.InputFrame):
            raise Exception("Incorrect input type for frame")
        if computation_type != ComputationType.OBJECT_DETECT:
            raise Exception("Computation type not supported")

        logger.info("Sending work item to local compute engine")

        await self.socket.send(frame.SerializeToString())
        result = await self.socket.recv()
        logger.info(f"Received response {result} from local compute engine")

async def main():
    logger.info("Starting local compute client")
    client = LocalComputeClient()
    frame = gabriel_pb2.InputFrame()
    result = await client.process_frame(frame, ComputationType.OBJECT_DETECT)
    while True:
        pass

if __name__ == "__main__":
    asyncio.run(main())
