#!/usr/bin/env python3
import asyncio
import json
import time
import zmq
import zmq.asyncio
from .datatypes.telemetry import DriverTelemetry
from .datatypes.result import FrameResult
from ..protocol.messages import telemetry_pb2 as telem_proto
from ..protocol.messages import result_pb2 as result_proto
from google.protobuf.json_format import MessageToDict
from .datatypes._base import Datatype

import logging
logger = logging.getLogger(__name__)

class MissionStore:
    def __init__(self, telemetry_addr, results_addr):
        self.ctx = zmq.asyncio.Context.instance()
        self.telemetry_addr = telemetry_addr
        self.results_addr = results_addr
        self._lock = asyncio.Lock()
        self._tasks = []
        self._telemetry = None
        self._results = None
        self._store = {}
        
    def _parse_payload(self, source, payload):
        result = None
        try:
            if source == 'telemetry':
                msg  = telem_proto.DriverTelemetry()
                msg.ParseFromString(payload)
                data = MessageToDict(msg, preserving_proto_field_name=True)
                result = DriverTelemetry.model_validate(data)
            # elif source == 'results':
            #     msg  = result_proto.FrameResult()
            #     msg.ParseFromString(payload)
            #     # logger.info(f"msg: {msg}")
            #     data = MessageToDict(msg, preserving_proto_field_name=True)
            #     # logger.info(f"data: {data}")
            #     result = FrameResult.model_validate(data)
        except Exception as e:
            logger.info(f"error: {e}")
        return result

    async def _consume(self, source, sock):
        while True:
            frames = await sock.recv_multipart()
            topic, payload = frames
            if topic == b'telemetry':
                continue # ignore the telemetry engine output
            parsed_res = self._parse_payload(source, payload)
            async with self._lock:
                self._store[(source, topic)] = parsed_res

    async def start(self):
        logger.info("Starting MissionStore")
        self._telemetry = self.ctx.socket(zmq.SUB)
        self._telemetry.setsockopt(zmq.SUBSCRIBE, b"")
        self._telemetry.connect(self.telemetry_addr)

        self._results = self.ctx.socket(zmq.SUB)
        self._results.setsockopt(zmq.SUBSCRIBE, b"")
        self._results.connect(self.results_addr)

        self._tasks = [
            asyncio.create_task(self._consume("telemetry", self._telemetry)),
            asyncio.create_task(self._consume("results", self._results)),
        ]

    async def stop(self):
        logger.info("Stopping MissionStore")
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        if self._telemetry:
            self._telemetry.close(0)
        if self._results:
            self._results.close(0)

    async def get_latest(self, source, topic) -> Datatype:
        async with self._lock:
            return self._store.get((source, topic))

    async def snapshot(self):
        async with self._lock:
            return dict(self._store)