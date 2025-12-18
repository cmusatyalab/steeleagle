import asyncio
import logging

import grpc
from google.protobuf import text_format
from steeleagle_sdk.protocol.services import remote_service_pb2 as remote_pb
from steeleagle_sdk.protocol.services import remote_service_pb2_grpc as remote_grpc

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class SwarmControllerClient:
    def __init__(self):
        target = "localhost:5004"
        self._channel = grpc.aio.insecure_channel(target)
        self._stub = remote_grpc.RemoteStub(self._channel)
        self._md = [("identity", "sc_client")]

    async def CompileMission(self, path: str):
        dsl = open(path, "r", encoding="utf-8").read()
        logger.info(f"Uploading: {dsl}")
        req = remote_pb.CompileMissionRequest(dsl_content=dsl)
        return await self._stub.CompileMission(req, metadata=self._md)


async def main():
    client = SwarmControllerClient()
    try:
        logger.info("Commands: upload <path>, start, stop, quit")
        while True:
            cmd = input("> ").strip().split()
            if not cmd:
                continue
            if cmd[0] == "upload" and len(cmd) == 2:
                resp = await client.CompileMission(cmd[1])
                logger.info(f"Upload response: {text_format.MessageToString(resp)}")
            elif cmd[0] == "start":
                resp = await client.Start()
                logger.info(f"Start response: {resp}")
            elif cmd[0] == "stop":
                resp = await client.Stop()
                logger.info(f"Stop response: {resp}")
            elif cmd[0] in ("quit", "exit"):
                break
            else:
                logger.warning("Unknown command")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
