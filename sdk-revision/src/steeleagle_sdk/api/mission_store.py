#!/usr/bin/env python3
import asyncio, time, json, logging
from typing import Optional, Any
import aiosqlite
import zmq, zmq.asyncio
from google.protobuf.json_format import MessageToDict

# --- your types/protos ---
from .datatypes._base import Datatype
from .datatypes.telemetry import DriverTelemetry
from .datatypes.result import FrameResult
from ..protocol.messages import telemetry_pb2 as telem_proto
from ..protocol.messages import result_pb2 as result_proto

logger = logging.getLogger(__name__)

INIT_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=3000;

CREATE TABLE IF NOT EXISTS latest (
  source TEXT NOT NULL,
  topic  TEXT NOT NULL,
  ts     REAL NOT NULL,
  payload_json TEXT NOT NULL,
  PRIMARY KEY (source, topic)
);
"""

SQL_UPSERT_LATEST = """
INSERT INTO latest(source, topic, ts, payload_json) VALUES(?,?,?,?)
ON CONFLICT(source, topic) DO UPDATE SET
  ts=excluded.ts,
  payload_json=excluded.payload_json
"""

SQL_SELECT_LATEST = "SELECT payload_json FROM latest WHERE source=? AND topic=?"

class MissionStore:
    # ---------- utils ----------
    @staticmethod
    def _norm_topic(b: bytes) -> str:
        return b.decode("utf-8", errors="ignore")

    @staticmethod
    def _to_json(model: Any) -> str:
        if model is None:
            return "null"
        try:
            return json.dumps(model.model_dump())  # pydantic v2
        except Exception:
            return json.dumps(model, default=lambda o: getattr(o, "__dict__", str(o)))

    @staticmethod
    def _from_json(source: str, payload_json: str):
        try:
            data = json.loads(payload_json)
            if data is None:
                return None
            if source == "telemetry":
                return DriverTelemetry.model_validate(data)
            if source == "results":
                return FrameResult.model_validate(data)
        except Exception:
            logger.exception("Decode failed for %s", source)
        return None

    def __init__(self, telemetry_addr: str, results_addr: str, db_path: str = "mission.db"):
        self.telemetry_addr = telemetry_addr
        self.results_addr = results_addr
        self.db_path = db_path

        self.db: Optional[aiosqlite.Connection] = None
        self.ctx = zmq.asyncio.Context(io_threads=2)

        self._telemetry = None
        self._results = None
        self._tasks: list[asyncio.Task] = []

    # ---------- store ----------
    def _parse_payload(self, source: str, payload: bytes):
        try:
            if source == "telemetry":
                msg = telem_proto.DriverTelemetry(); msg.ParseFromString(payload)
                data = MessageToDict(msg, preserving_proto_field_name=True)
                return DriverTelemetry.model_validate(data)
            # elif source == "results":
                # msg = result_proto.FrameResult(); msg.ParseFromString(payload)
                # data = MessageToDict(msg, preserving_proto_field_name=True)
                # return FrameResult.model_validate(data)
        except Exception:
            logger.exception("Parse failed for %s payload", source)
        return None
    
    async def _receive_and_store(self, source: str, sock: zmq.asyncio.Socket):
        try:
            while True:
                frames = await sock.recv_multipart()
                if not frames:
                    continue
                topic = self._norm_topic(frames[0])
                if topic == b'telemetry':
                    continue # ignore telmetry engine
                payload = frames[-1]

                model = self._parse_payload(source, payload)
                ts = time.time()
                pj = self._to_json(model)

                try:
                    await self.db.execute(SQL_UPSERT_LATEST, (source, topic, ts, pj))
                    await self.db.commit()
                except Exception:
                    logger.exception("DB upsert failed for %s/%s", source, topic)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Consumer crashed (%s)", source)
    
    # ---------- reads ----------
    async def get_latest(self, source: str, topic: str) -> Datatype:
        """Read latest from DB and return decoded model (no cache)."""
        await asyncio.sleep(0)
        async with self.db.execute(SQL_SELECT_LATEST, (source, topic)) as cur:
            row = await cur.fetchone()
            if not row:
                return None
            (payload_json,) = row
            return self._from_json(source, payload_json)

    # ---------- lifecycle ----------
    async def start(self):
        self.db = await aiosqlite.connect(self.db_path)
        await self.db.executescript(INIT_SQL)
        await self.db.commit()

        self._telemetry = self.ctx.socket(zmq.SUB)
        self._telemetry.setsockopt(zmq.SUBSCRIBE, b"")
        self._telemetry.setsockopt(zmq.RCVHWM, 1000)
        self._telemetry.connect(self.telemetry_addr)

        self._results = self.ctx.socket(zmq.SUB)
        self._results.setsockopt(zmq.SUBSCRIBE, b"")
        self._results.setsockopt(zmq.RCVHWM, 1000)
        self._results.connect(self.results_addr)

        self._tasks = [
            asyncio.create_task(self._receive_and_store("telemetry", self._telemetry)),
            # asyncio.create_task(self._receive_and_store("results", self._results)),
        ]

    async def stop(self):
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        if self._telemetry: self._telemetry.close(0); self._telemetry = None
        if self._results:   self._results.close(0);   self._results = None
        if self.db:         await self.db.close();    self.db = None