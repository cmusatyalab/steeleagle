# persistent_mission_client.py
import asyncio
import json
import signal
import grpc

from util.config import query_config
from steeleagle_sdk.protocol.services import mission_service_pb2 as mission_pb
from steeleagle_sdk.protocol.services import mission_service_pb2_grpc as mission_grpc
from google.protobuf import text_format

class MissionClient:
    def __init__(self):
        # Initialize once and keep it around
        target = query_config('internal.services.kernel')
        self._channel = grpc.aio.insecure_channel(target)
        self._stub = mission_grpc.MissionStub(self._channel)
        self._md = [('identity', 'authority')]  
    
    async def close(self):               
        await self._channel.close()

    # --- API helpers ---
    async def upload_text(self, mission_json_text: str):
        # (server parses it with json.loads)
        json.loads(mission_json_text)  # sanity check
        req = mission_pb.UploadRequest(mission=mission_pb.Mission(content=mission_json_text), metadata=self._md)
        return await self._stub.Upload(req)

    async def Upload(self, path: str):
        text = open(path, "r", encoding="utf-8").read()
        return await self.upload_text(text)

    async def Start(self):
        return await self._stub.Start(mission_pb.StartRequest(), metadata=self._md)

    async def Stop(self):
        return await self._stub.Stop(mission_pb.StopRequest(), metadata=self._md)


# --- optional: simple daemon-style entrypoint ---
async def main():
    client = MissionClient()
    try:
        print("Commands: upload <path>, start, stop, quit")
        while True:
            cmd = input("> ").strip().split()
            if not cmd:
                continue
            if cmd[0] == "upload" and len(cmd) == 2:
                resp = await client.Upload(cmd[1])
                print(text_format.MessageToString(resp))  
            elif cmd[0] == "start":
                resp = await client.Start()
                print(f"status={resp.response.status} "
                      f"msg={resp.response.response_string} "
                      f"ts={resp.response.timestamp.ToDatetime().isoformat()}")
            elif cmd[0] == "stop":
                resp = await client.Stop()
                print("Stop JSON ->", text_format.MessageToString(resp))
            elif cmd[0] in ("quit", "exit"):
                break
            else:
                print("Unknown command")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
