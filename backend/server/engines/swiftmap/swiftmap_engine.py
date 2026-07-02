#!/usr/bin/env python3
# Copyright (C) 2026 Carnegie Mellon University
# Licensed under the Apache License, Version 2.0 (the "License");
#
# SwiftMap cognitive engine for the SteelEagle / Gabriel backend.
#
# Receives Gabriel input frames (a steeleagle_sdk telemetry.Frame carried in the
# input frame's any_payload), decodes the image and the *paired* GPS from
# frame.position_info.global_position, and forwards both to a running SwiftMap
# mapping server over TCP. SwiftMap performs keyframe selection + 3D reconstruction
# internally. No meaningful result is returned to the Gabriel client for now.
#
# This engine targets the modern Gabriel/SteelEagle API (matches the aruco and
# telemetry engines), NOT the legacy SLAM engine pattern.

import logging
import socket
import struct
import time

import cv2
import numpy as np
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine
from steeleagle_sdk.protocol.messages import telemetry_pb2 as telemetry

logger = logging.getLogger(__name__)


class SwiftMapClient:
    """TCP client to the SwiftMap mapping server.

    Protocol per frame: 4-byte big-endian image size, JPEG bytes, then the paired
    GPS as 3 big-endian float64 (lat, lon, alt; NaN = no GPS). The server replies
    with 3 native-order float64 (status, keyframe_count, total_frames).
    """

    def __init__(self, server_ip="localhost", server_port=43322):
        self.server_ip = server_ip
        self.server_port = server_port
        self.client_socket = None
        self.connected = False
        self.retry_interval = 5   # seconds between reconnect attempts at startup
        self.socket_timeout = 15  # seconds before a send/recv is treated as dead

    def _close_socket(self):
        """Drop the current socket and mark the client disconnected."""
        if self.client_socket is not None:
            try:
                self.client_socket.close()
            except Exception:
                pass
            self.client_socket = None
        self.connected = False

    def connect(self, max_retries=None):
        """(Re)connect to the SwiftMap server.

        max_retries=None retries forever (startup). A finite value makes at most
        that many attempts then returns False, used for a fast best-effort
        reconnect mid-stream so a dead frame doesn't block the engine while the
        server is down.
        """
        attempt = 0
        while max_retries is None or attempt < max_retries:
            attempt += 1
            self._close_socket()
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.socket_timeout)
                sock.connect((self.server_ip, self.server_port))
                self.client_socket = sock
                self.connected = True
                logger.info(
                    f"Connected to SwiftMap server at {self.server_ip}:{self.server_port}"
                )
                return True
            except Exception as e:
                logger.error(f"Failed to connect to SwiftMap server: {e}")
                if max_retries is not None and attempt >= max_retries:
                    break
                logger.info(f"Retrying connection in {self.retry_interval} seconds...")
                time.sleep(self.retry_interval)
        return False

    def process_frame(self, image_data, gps):
        """Send a frame + paired GPS to SwiftMap. gps = (lat, lon, alt) or None.

        Survives a SwiftMap server restart: if the socket is dead, it makes a
        best-effort reconnect and retries the frame once. If the server is still
        down the frame is dropped ("error") and the next frame retries — the
        engine keeps running throughout.
        """
        # Decode + re-encode the image to guarantee a clean JPEG payload. A decode
        # failure is a bad frame, not a connection problem, so don't reconnect.
        np_data = np.frombuffer(image_data, dtype=np.uint8)
        img = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        if img is None:
            logger.error("Failed to decode incoming image")
            return "error"
        _, img_encoded = cv2.imencode(".jpg", img)
        img_bytes = img_encoded.tobytes()
        lat, lon, alt = gps if gps is not None else (float("nan"),) * 3
        header = struct.pack("!I", len(img_bytes))
        gps_bytes = struct.pack("!3d", lat, lon, alt)

        # Two passes: send on the current connection; if it's dead, reconnect once
        # and resend. The frame is length-prefixed, so resending on a fresh socket
        # is a clean new frame (no desync with a partially-sent old one).
        for attempt in range(2):
            if not self.connected and not self.connect(max_retries=1):
                return "error"  # server still down; drop this frame, retry next one
            try:
                self.client_socket.sendall(header)
                self.client_socket.sendall(img_bytes)
                self.client_socket.sendall(gps_bytes)

                resp = b""
                while len(resp) < 24:
                    chunk = self.client_socket.recv(24 - len(resp))
                    if not chunk:
                        raise ConnectionError("SwiftMap server closed the connection")
                    resp += chunk
                status, _kf, _total = struct.unpack("3d", resp)
                return "keyframe" if status == 1.0 else "skipped"
            except Exception as e:
                logger.warning(
                    f"SwiftMap connection lost ({e}); reconnecting"
                    + (" and retrying frame" if attempt == 0 else "")
                )
                self._close_socket()  # forces a reconnect on the next pass
        return "error"

    def close(self):
        self._close_socket()
        logger.info("SwiftMap connection closed")


class SwiftMapEngine(cognitive_engine.Engine):
    ENGINE_NAME = "swiftmap"

    def __init__(self, args):
        self.server_ip = args.server
        self.server_port = args.server_port

        self.client = SwiftMapClient(server_ip=self.server_ip, server_port=self.server_port)
        if not self.client.connect():
            raise Exception("Failed to connect to SwiftMap server")

        # Timing stats
        self.count = 0
        self.lastcount = 0
        self.lastprint = time.time()

    @staticmethod
    def _extract_gps(frame):
        """Pull (lat, lon, alt) from frame.position_info.global_position, or None."""
        try:
            pos = frame.position_info.global_position
            if pos.HasField("latitude") and pos.HasField("longitude"):
                alt = pos.altitude if pos.HasField("altitude") else 0.0
                return (pos.latitude, pos.longitude, alt)
        except Exception:
            pass
        return None

    def handle(self, input_frame):
        status = gabriel_pb2.Status()

        # SwiftMap only consumes IMAGE frames (the telemetry.Frame carries both the
        # image bytes and the paired GPS).
        if input_frame.payload_type != gabriel_pb2.PayloadType.IMAGE:
            status.code = gabriel_pb2.StatusCode.WRONG_INPUT_FORMAT
            status.message = f"Ignoring non-image payload: {input_frame.payload_type}"
            return cognitive_engine.Result(status, None)

        # Unpack the modern steeleagle_sdk Frame from the input frame's any_payload.
        frame = telemetry.Frame()
        if input_frame.WhichOneof("payload") != "any_payload" or not input_frame.any_payload.Is(
            telemetry.Frame.DESCRIPTOR
        ):
            status.code = gabriel_pb2.StatusCode.WRONG_INPUT_FORMAT
            status.message = "Expected an any_payload telemetry.Frame"
            return cognitive_engine.Result(status, None)
        input_frame.any_payload.Unpack(frame)

        gps = self._extract_gps(frame)

        # Forward the image + paired GPS to the SwiftMap mapping server.
        send_status = self.client.process_frame(frame.data, gps)
        if send_status == "error":
            status.code = gabriel_pb2.StatusCode.ENGINE_ERROR
            status.message = "Failed to forward frame to SwiftMap server"
            return cognitive_engine.Result(status, None)

        self.count += 1
        now = time.time()
        if now - self.lastprint > 5:
            self.print_inference_stats(now)

        # No meaningful result back to the Gabriel client for now.
        return cognitive_engine.Result(status, send_status)

    def print_inference_stats(self, now=None):
        now = now or time.time()
        fps = (self.count - self.lastcount) / max(now - self.lastprint, 1e-9)
        logger.info(f"swiftmap engine avg fps: {fps:.2f} (total frames: {self.count})")
        self.lastcount = self.count
        self.lastprint = now
