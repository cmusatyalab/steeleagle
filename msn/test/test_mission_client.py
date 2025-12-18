# persistent_mission_client.py
import asyncio
import json
import logging
from dataclasses import asdict

import grpc
from google.protobuf import text_format
from steeleagle_sdk.dsl import build_mission
from steeleagle_sdk.protocol.services import mission_service_pb2 as mission_pb
from steeleagle_sdk.protocol.services import mission_service_pb2_grpc as mission_grpc
from util.config import query_config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MissionClient:
    def __init__(self):
        # Initialize once and keep it around
        target = query_config("internal.services.kernel")
        self._channel = grpc.aio.insecure_channel(target)
        self._stub = mission_grpc.MissionStub(self._channel)
        self._md = [("identity", "server")]

    async def close(self):
        await self._channel.close()

    # --- API helpers ---
    def compile_dsl(self, dsl: str):
        # (server parses it with json.loads)
        mission = build_mission(dsl)
        logger.info(f"Built mission: {mission}")
        mission_json_text = json.dumps(asdict(mission))
        return mission_json_text

    async def Upload(self, path: str):
        dsl = open(path, "r", encoding="utf-8").read()
        logger.info(f"Uploading: {dsl}")
        mission_json_text = self.compile_dsl(dsl)
        logger.info(f"Compiled JSON -> {mission_json_text}")
        req = mission_pb.UploadRequest(
            mission=mission_pb.MissionData(content=mission_json_text)
        )
        return await self._stub.Upload(req, metadata=self._md)

    async def Start(self):
        return await self._stub.Start(mission_pb.StartRequest(), metadata=self._md)

    async def Stop(self):
        return await self._stub.Stop(mission_pb.StopRequest(), metadata=self._md)


# --- optional: simple daemon-style entrypoint ---
async def main():
    client = MissionClient()
    try:
        logger.info("Commands: upload <path>, start, stop, quit")
        while True:
            cmd = input("> ").strip().split()
            if not cmd:
                continue
            if cmd[0] == "upload" and len(cmd) == 2:
                resp = await client.Upload(cmd[1])
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
