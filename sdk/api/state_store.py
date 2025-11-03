#!/usr/bin/env python3
import asyncio
import json
import time
import zmq
import zmq.asyncio
import logging

logger = logging.getLogger(__name__)

class StateStore:
    def __init__(self,
                 telemetry_sock="ipc:///tmp/driver_telem.sock",
                 results_sock="ipc:///tmp/results.sock"):
        self.ctx = zmq.asyncio.Context.instance()
        self.telemetry_addr = telemetry_sock
        self.results_addr = results_sock
        self.cache = {}                 # {(source, topic): {payload, timestamp}}
        self._lock = asyncio.Lock()     # async-safe guard
        self._tasks = []
        self._telemetry = None
        self._results = None

    @staticmethod
    def _decode_payload(b: bytes):
        try:
            s = b.decode()
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                return s
        except UnicodeDecodeError:
            return b

    def _parse_frames(self, frames):
        if len(frames) == 1:
            return "__raw__", self._decode_payload(frames[0])
        topic = frames[0].decode(errors="ignore")
        payload = self._decode_payload(frames[-1])
        return topic, payload

    async def _consume(self, source, sock):
        while True:
            frames = await sock.recv_multipart()
            topic, payload = self._parse_frames(frames)
            async with self._lock:
                self.cache[(source, topic)] = {"payload": payload, "timestamp": time.time()}

    async def start(self):
        logger.info("Starting StateStore")
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
        logger.info("Stopping StateStore")
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        if self._telemetry:
            self._telemetry.close(0)
        if self._results:
            self._results.close(0)
        # self.ctx.term()  # uncomment if this is the only ZMQ user

    async def get_latest(self, source, topic):
        async with self._lock:
            logger.info(f"Getting latest for {source}, {topic}")
            return self.cache.get((source, topic))

    async def snapshot(self):
        async with self._lock:
            return dict(self.cache)