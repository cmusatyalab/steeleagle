#!/usr/bin/env python3
# Copyright (C) 2026 Carnegie Mellon University
# Licensed under the Apache License, Version 2.0 (the "License").
"""SwiftMap cognitive engine: forwards Gabriel telemetry.Frame (image + paired GPS)
to a running SwiftMap mapping server over TCP.
"""

import logging
import math
import socket
import struct
import time
import cv2
import numpy as np
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine
from google.protobuf.any_pb2 import Any
from steeleagle_sdk.protocol.messages import telemetry_pb2 as telemetry
from steeleagle_sdk.protocol.messages import result_pb2

logger = logging.getLogger(__name__)

# Helper Func for gps to meter conversion
_EARTH_RADIUS_M = 6_371_000.0

def _haversine_m(a, b) -> float:
    """Great-circle distance in meters between two (lat, lon, alt) points."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))

# Wire: client sends [BE uint32 size][JPEG][24-byte GPS]; server replies with 3
# float64 (status, keyframe_count, total) followed by a big-endian uint32 length and
# an optional trailing payload (an NFN area KML; length 0 for an ordinary ack).
DEFAULT_PORT = 43322
SIZE_FMT = "!I"    # image-size header
GPS_FMT = "!3d"    # lat, lon, alt (NaN triple = no GPS)
REPLY_FMT = "3d"   # status, keyframe_count, total_frames
REPLY_NBYTES = struct.calcsize(REPLY_FMT)
PAYLOAD_LEN_FMT = "!I"   # 4-byte big-endian length of the trailing reply payload
PAYLOAD_LEN_NBYTES = struct.calcsize(PAYLOAD_LEN_FMT)
STATUS_KEYFRAME = 1.0

RETRY_INTERVAL = 5   # seconds between blocking reconnect attempts
SOCKET_TIMEOUT = 15  # seconds before a connect/send/recv is dead


class SwiftMapClient:
    """TCP client to the SwiftMap mapping server (see wire protocol above)."""

    def __init__(self, server_ip="localhost", server_port=DEFAULT_PORT):
        self.server_ip = server_ip
        self.server_port = server_port
        self.sock = None
        self.connected = False

    def _close(self):
        """Close the socket and mark the client disconnected."""
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
        self.connected = False

    def connect(self, max_retries=None):
        """
        Connect with retries.
        """ 
        attempt = 0
        while max_retries is None or attempt < max_retries:
            attempt += 1
            self._close()
            try:
                self.sock = socket.create_connection(
                    (self.server_ip, self.server_port), timeout=SOCKET_TIMEOUT)
                self.connected = True
                logger.info("Connected to SwiftMap server at %s:%s",
                            self.server_ip, self.server_port)
                return True
            except OSError as e:
                logger.error("Failed to connect to SwiftMap server: %s", e)
                if max_retries is not None and attempt >= max_retries:
                    return False
                logger.info("Retrying in %ss...", RETRY_INTERVAL)
                time.sleep(RETRY_INTERVAL)
        return False

    def _recv_exact(self, n):
        """Read exactly ``n`` bytes, or None if the peer closes early."""
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def _recv_reply(self):
        """Read the status reply plus any length-prefixed trailing payload."""
        head = self._recv_exact(REPLY_NBYTES)
        if head is None:
            return None
        status, _kf, _total = struct.unpack(REPLY_FMT, head)
        len_buf = self._recv_exact(PAYLOAD_LEN_NBYTES)
        if len_buf is None:
            return None
        n = struct.unpack(PAYLOAD_LEN_FMT, len_buf)[0]
        payload = b""
        if n:
            payload = self._recv_exact(n)
            if payload is None:
                return None
        return status, payload

    def process_frame(self, image_data, gps):
        """Forward one frame + paired GPS"""
        # Try decoding to test the frame validity
        img = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            logger.error("Failed to decode incoming image")
            return "error", b""

        # Encode the frame
        img_bytes = cv2.imencode(".jpg", img)[1].tobytes()

        if gps is None:
            logger.error("Failed to receive gps")
            return "error", b""
        lat, lon, alt = gps

        payload = (struct.pack(SIZE_FMT, len(img_bytes)) + img_bytes
                   + struct.pack(GPS_FMT, lat, lon, alt))

        # Send; if the socket is dead, reconnect once and resend.
        for attempt in range(2):
            if not self.connected and not self.connect(max_retries=1):
                return "error", b""
            try:
                self.sock.sendall(payload)
                reply = self._recv_reply()
                if reply is None:
                    raise ConnectionError("server closed the connection")
                status, back = reply
                return ("keyframe" if status == STATUS_KEYFRAME else "skipped"), back
            except OSError as e:
                retrying = " and retrying frame" if attempt == 0 else ""
                logger.warning("SwiftMap connection lost (%s); reconnecting%s", e, retrying)
                self._close()
        return "error", b""

    def close(self):
        self._close()
        logger.info("SwiftMap connection closed")


class SwiftMapEngine(cognitive_engine.Engine):
    ENGINE_NAME = "swiftmap"
    STATS_INTERVAL = 5  # seconds between fps log lines
    NAV_HOLD_S = 3.0    # re-emit a new plan for this long so it survives the CONFLATE results channel

    def __init__(self, args):
        self.client = SwiftMapClient(args.server, args.server_port)

        # The engine registers with Gabriel and reconnects per-frame in process_frame.
        if not self.client.connect(max_retries=1):
            logger.warning("SwiftMap server at %s:%s not reachable yet; engine is up "
                           "and will connect on the first frame.",
                           args.server, args.server_port)

        # Forward at most one pair per gps lapse.
        self.send_distance = float(getattr(args, "send_distance", 5.0))
        self._last_sent_gps = None
        self._nav_kml = None       # current NFN plan KML, re-emitted during its hold window
        self._nav_until = 0.0      # wall-clock deadline for re-emitting the current plan
        self.count = 0        # frames received
        self.sent = 0         # frames forwarded to the server
        self.last_count = 0
        self.last_stats = time.time()
        logger.info("SwiftMap engine: forwarding one pair per %.1f m of travel",
                    self.send_distance)

    @staticmethod
    def _extract_gps(frame):
        """Return (lat, lon, alt) from the frame's global position, or None."""
        try:
            pos = frame.position_info.global_position
            if pos.HasField("latitude") and pos.HasField("longitude"):
                alt = pos.altitude if pos.HasField("altitude") else 0.0
                return (pos.latitude, pos.longitude, alt)
        except Exception:
            return None
        return None

    def _log_stats(self):
        """Log average fps once per STATS_INTERVAL."""
        self.count += 1
        elapsed = time.time() - self.last_stats
        if elapsed > self.STATS_INTERVAL:
            fps = (self.count - self.last_count) / elapsed
            logger.info("swiftmap engine avg fps: %.2f (received: %d, forwarded: %d)",
                        fps, self.count, self.sent)
            self.last_count = self.count
            self.last_stats += elapsed

    def _frame_result_any(self, nav_kml=None):
        """Pack a FrameResult as a Gabriel Any: empty, or carrying the NFN area KML.

        The mission store ignores empty (no-result) FrameResults, so ordinary
        per-frame acks don't overwrite the latest plan.
        """
        frame_result = result_pb2.FrameResult()
        frame_result.type = "swiftmap-navigation"
        if nav_kml is not None:
            compute = frame_result.result.add()
            compute.engine_name = self.ENGINE_NAME
            compute.navigation_result.area_kml = nav_kml.decode("utf-8", "replace")
        frame_result.timestamp.GetCurrentTime()
        any_payload = Any()
        any_payload.Pack(frame_result)
        return any_payload

    def handle(self, input_frame):
        status = gabriel_pb2.Status()

        if input_frame.payload_type != gabriel_pb2.PayloadType.IMAGE:
            status.code = gabriel_pb2.StatusCode.WRONG_INPUT_FORMAT
            status.message = f"Ignoring non-image payload: {input_frame.payload_type}"
            return cognitive_engine.Result(status, None)
        if (input_frame.WhichOneof("payload") != "any_payload"
                or not input_frame.any_payload.Is(telemetry.Frame.DESCRIPTOR)):
            status.code = gabriel_pb2.StatusCode.WRONG_INPUT_FORMAT
            status.message = "Expected an any_payload telemetry.Frame"
            return cognitive_engine.Result(status, None)

        frame = telemetry.Frame()
        input_frame.any_payload.Unpack(frame)
        self._log_stats()
        gps = self._extract_gps(frame)

        # Distance gate: forward at most one pair per send_distance of travel.
        gated = self.send_distance > 0 and (
            gps is None
            or (self._last_sent_gps is not None
                and _haversine_m(self._last_sent_gps, gps) < self.send_distance))

        if not gated:
            send_status, nfn_kml = self.client.process_frame(frame.data, gps)
            if send_status == "error":
                status.code = gabriel_pb2.StatusCode.ENGINE_ERROR
                status.message = "SwiftMap server unreachable; frame dropped"
                logger.warning("SwiftMap server unreachable; frame dropped")
                return cognitive_engine.Result(status, None)
            self._log_stats()
            self._last_sent_gps = gps
            self.sent += 1
            if nfn_kml:
                self._nav_kml = nfn_kml
                self._nav_until = time.time() + self.NAV_HOLD_S
                logger.info("Received NFN area KML from SwiftMap server (%d bytes); "
                            "holding it as the current plan for %.1fs",
                            len(nfn_kml), self.NAV_HOLD_S)

        # Re-emit the current plan on every frame within its hold window so it survives
        # the CONFLATE results channel (both ends keep only the latest message).
        if self._nav_kml is not None and time.time() < self._nav_until:
            return cognitive_engine.Result(status, self._frame_result_any(self._nav_kml))
        return cognitive_engine.Result(status, self._frame_result_any())
