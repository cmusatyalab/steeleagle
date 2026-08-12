#!/usr/bin/env python3
# Copyright (C) 2026 Carnegie Mellon University
# Licensed under the Apache License, Version 2.0 (the "License").
"""SwiftMap cognitive engine: forwards Gabriel telemetry.Frame (image + paired GPS)
to a running SwiftMap mapping server over TCP.

To avoid overfilling the server, frames are *distance-gated*: only one frame+GPS
pair is forwarded per ``send_distance`` meters of drone travel (haversine on the
GPS). The server still does its own keyframe selection on what it receives."""

import logging
import math
import socket
import struct
import time

import cv2
import numpy as np
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine
from steeleagle_sdk.protocol.messages import telemetry_pb2 as telemetry

logger = logging.getLogger(__name__)

_EARTH_RADIUS_M = 6_371_000.0


def _haversine_m(a, b) -> float:
    """Great-circle distance in meters between two (lat, lon, alt) points."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


# Wire: client sends [BE uint32 size][JPEG][24-byte GPS]; server replies with 3
# float64 (status, keyframe_count, total).
# TODO: mirror of swift_map's swiftmap/core/protocol.py; import it once swift_map
# ships an installable lib (keep in sync until then).
DEFAULT_PORT = 43322
SIZE_FMT = "!I"  # image-size header
GPS_FMT = "!3d"  # lat, lon, alt (NaN triple = no GPS)
REPLY_FMT = "3d"  # status, keyframe_count, total_frames
REPLY_NBYTES = struct.calcsize(REPLY_FMT)
STATUS_KEYFRAME = 1.0

RETRY_INTERVAL = 5  # seconds between blocking reconnect attempts
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
        """(Re)connect. max_retries=None retries forever; a finite value tries that
        many times then returns False (fast best-effort reconnect)."""
        attempt = 0
        while max_retries is None or attempt < max_retries:
            attempt += 1
            self._close()
            try:
                self.sock = socket.create_connection(
                    (self.server_ip, self.server_port), timeout=SOCKET_TIMEOUT
                )
                self.connected = True
                logger.info(
                    "Connected to SwiftMap server at %s:%s",
                    self.server_ip,
                    self.server_port,
                )
                return True
            except OSError as e:
                logger.error("Failed to connect to SwiftMap server: %s", e)
                if max_retries is not None and attempt >= max_retries:
                    return False
                logger.info("Retrying in %ss...", RETRY_INTERVAL)
                time.sleep(RETRY_INTERVAL)
        return False

    def _recv_reply(self):
        """Read the fixed-size status reply, or None if the peer closes early."""
        buf = b""
        while len(buf) < REPLY_NBYTES:
            chunk = self.sock.recv(REPLY_NBYTES - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def process_frame(self, image_data, gps):
        """Forward one frame + paired GPS; return its status string. On a dead socket,
        reconnects and retries once, else drops the frame ("error")."""
        # A decode failure is a bad frame, not a connection problem: don't retry.
        img = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            logger.error("Failed to decode incoming image")
            return "error"
        img_bytes = cv2.imencode(".jpg", img)[1].tobytes()
        lat, lon, alt = gps if gps is not None else (float("nan"),) * 3
        payload = (
            struct.pack(SIZE_FMT, len(img_bytes))
            + img_bytes
            + struct.pack(GPS_FMT, lat, lon, alt)
        )

        # Send; if the socket is dead, reconnect once and resend (frames are
        # length-prefixed, so a resend on a fresh socket is clean).
        for attempt in range(2):
            if not self.connected and not self.connect(max_retries=1):
                return "error"
            try:
                self.sock.sendall(payload)
                reply = self._recv_reply()
                if reply is None:
                    raise ConnectionError("server closed the connection")
                status, _kf, _total = struct.unpack(REPLY_FMT, reply)
                return "keyframe" if status == STATUS_KEYFRAME else "skipped"
            except OSError as e:
                retrying = " and retrying frame" if attempt == 0 else ""
                logger.warning(
                    "SwiftMap connection lost (%s); reconnecting%s", e, retrying
                )
                self._close()
        return "error"

    def close(self):
        self._close()
        logger.info("SwiftMap connection closed")


class SwiftMapEngine(cognitive_engine.Engine):
    ENGINE_NAME = "swiftmap"
    STATS_INTERVAL = 5  # seconds between fps log lines

    def __init__(self, args):
        self.client = SwiftMapClient(args.server, args.server_port)
        # Best-effort only: don't block startup on the mapping server. The engine
        # registers with Gabriel and reconnects per-frame in process_frame.
        if not self.client.connect(max_retries=1):
            logger.warning(
                "SwiftMap server at %s:%s not reachable yet; engine is up "
                "and will connect on the first frame.",
                args.server,
                args.server_port,
            )
        # Forward at most one pair per this many meters of travel (0 = every frame).
        self.send_distance = float(getattr(args, "send_distance", 5.0))
        self._last_sent_gps = None
        self.count = 0  # frames received
        self.sent = 0  # frames forwarded to the server
        self.last_count = 0
        self.last_stats = time.time()
        logger.info(
            "SwiftMap engine: forwarding one pair per %.1f m of travel",
            self.send_distance,
        )

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

    def handle(self, input_frame):
        status = gabriel_pb2.Status()

        # Only IMAGE frames carry a telemetry.Frame (image bytes + paired GPS).
        if input_frame.payload_type != gabriel_pb2.PayloadType.IMAGE:
            status.code = gabriel_pb2.StatusCode.WRONG_INPUT_FORMAT
            status.message = f"Ignoring non-image payload: {input_frame.payload_type}"
            return cognitive_engine.Result(status, b"")
        if input_frame.WhichOneof(
            "payload"
        ) != "any_payload" or not input_frame.any_payload.Is(
            telemetry.Frame.DESCRIPTOR
        ):
            status.code = gabriel_pb2.StatusCode.WRONG_INPUT_FORMAT
            status.message = "Expected an any_payload telemetry.Frame"
            return cognitive_engine.Result(status, b"")

        frame = telemetry.Frame()
        input_frame.any_payload.Unpack(frame)
        self._log_stats()

        gps = self._extract_gps(frame)

        # Distance gate: forward at most one pair per send_distance meters. With
        # gating on, a frame must carry GPS (the pair is what the server maps from).
        if self.send_distance > 0:
            if gps is None:
                return cognitive_engine.Result(
                    status, "skipped"
                )  # no GPS -> can't pair
            if (
                self._last_sent_gps is not None
                and _haversine_m(self._last_sent_gps, gps) < self.send_distance
            ):
                return cognitive_engine.Result(status, "skipped")  # too close -> drop

        send_status = self.client.process_frame(frame.data, gps)
        if send_status == "error":
            logger.warning("SwiftMap server unreachable; frame dropped")
            return cognitive_engine.Result(status, b"")

        self._log_stats()
        # Only advance the reference once the pair is actually on its way.
        self._last_sent_gps = gps
        self.sent += 1
        return cognitive_engine.Result(status, send_status.encode())

    def _log_stats(self):
        """Log average fps once per STATS_INTERVAL."""
        self.count += 1
        elapsed = time.time() - self.last_stats
        if elapsed > self.STATS_INTERVAL:
            fps = (self.count - self.last_count) / elapsed
            logger.info(
                "swiftmap engine avg fps: %.2f (received: %d, forwarded: %d)",
                fps,
                self.count,
                self.sent,
            )
            self.last_count = self.count
            self.last_stats += elapsed
