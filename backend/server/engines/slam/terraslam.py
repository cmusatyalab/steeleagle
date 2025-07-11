#!/usr/bin/env python3
# OpenScout
#   - Distributed Automated Situational Awareness
#
#   Author: Jingao Xu <jingaox@andrew.cmu.edu>
#
#   Copyright (C) 2020 Carnegie Mellon University
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#
import json
import logging
import socket
import struct
import time

import cv2
import numpy as np
import redis
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine

import protocol.common_pb2 as common
import protocol.controlplane_pb2 as control_plane
import protocol.gabriel_extras_pb2 as gabriel_extras

logger = logging.getLogger(__name__)


class TerraSLAMClient:
    def __init__(self, server_ip="localhost", server_port=43322):
        self.server_ip = server_ip
        self.server_port = server_port
        self.client_socket = None
        self.latest_pose = None
        self.previous_pose = None
        self.retry_interval = 5  # Retry interval in seconds

    def connect(self):
        while True:
            try:
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((self.server_ip, self.server_port))
                logger.info(
                    f"Connected to SLAM server at {self.server_ip}:{self.server_port}"
                )
                return True
            except Exception as e:
                logger.error(f"Failed to connect to SLAM server: {e}")
                logger.info(f"Retrying connection in {self.retry_interval} seconds...")
                time.sleep(self.retry_interval)
                continue

    def process_image(self, image_data):
        """Process image data and send to SLAM server"""
        try:
            # Convert image data to numpy array
            np_data = np.fromstring(image_data, dtype=np.uint8)
            img = cv2.imdecode(np_data, cv2.IMREAD_COLOR)

            # Encode image for sending
            _, img_encoded = cv2.imencode(".jpg", img)
            img_bytes = img_encoded.tobytes()

            # Send image size
            size = len(img_bytes)
            self.client_socket.sendall(struct.pack("!I", size))

            # Send image data
            self.client_socket.sendall(img_bytes)

            # Receive pose data (3 doubles = 24 bytes)
            pose_data = self.client_socket.recv(24)
            if len(pose_data) == 24:
                x, y, z = struct.unpack("3d", pose_data)

                # Store previous pose before updating
                self.previous_pose = self.latest_pose
                self.latest_pose = (x, y, z)

                # Check if all values are -1.0 (initializing status)
                if x == -1.0 and y == -1.0 and z == -1.0:
                    logger.info("SLAM system status: Initializing")
                    return "initializing"

                # Check if tracking is lost (pose barely changes)
                if x == -3.0 and y == -3.0 and z == -3.0:
                    logger.info("SLAM system status: Tracking Lost")
                    return "lost"

                return "success"
            else:
                logger.error("Failed to receive complete pose data")
                return "error"

        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return "error"

    def close(self):
        if self.client_socket:
            self.client_socket.close()
            logger.info("SLAM connection closed")


class TerraSLAMEngine(cognitive_engine.Engine):
    ENGINE_NAME = "terra-slam"

    def __init__(self, args):
        self.server_ip = args.server
        self.server_port = 43322  # Fixed SLAM server port
        self.redis_port = args.redis
        self.redis_auth = args.auth

        # Initialize SLAM client
        self.slam_client = TerraSLAMClient(
            server_ip=self.server_ip, server_port=self.server_port
        )

        if not self.slam_client.connect():
            raise Exception("Failed to connect to SLAM server")

        # Initialize Redis connection
        self.r = redis.Redis(
            host="redis",
            port=self.redis_port,
            username="steeleagle",
            password=self.redis_auth,
            decode_responses=True,
        )
        try:
            self.r.ping()
            logger.info(f"Connected to redis on port {self.redis_port}...")
        except redis.ConnectionError:
            logger.error("Failed to connect to Redis")

        # Timing variables
        self.count = 0
        self.lasttime = time.time()
        self.lastcount = 0
        self.lastprint = self.lasttime

    def handle(self, input_frame):
        if input_frame.payload_type == gabriel_pb2.PayloadType.TEXT:
            return self.text_payload_reply()

        extras = cognitive_engine.unpack_extras(gabriel_extras.Extras, input_frame)

        if not extras.cpt_request.HasField("cpt"):
            status = gabriel_pb2.ResultWrapper.Status.UNSPECIFIED_ERROR
            result_wrapper = self.get_result_wrapper(status)
            result = gabriel_pb2.ResultWrapper.Result()
            result.payload_type = gabriel_pb2.PayloadType.TEXT
            result.payload = b"Expected compute configuration to be specified"
            result_wrapper.results.append(result)
            return result_wrapper

        # Process the image
        slam_status = self.slam_client.process_image(input_frame.payloads[0])

        status = gabriel_pb2.ResultWrapper.Status.SUCCESS
        result_wrapper = self.get_result_wrapper(status)

        # Construct response
        result = gabriel_pb2.ResultWrapper.Result()
        result.payload_type = gabriel_pb2.PayloadType.TEXT

        if slam_status == "success" and self.slam_client.latest_pose:
            # Get GPS coordinates
            lat, lon, alt = self.slam_client.latest_pose

            logger.info(f"GPS coordinates: {lat}, {lon}, {alt}")
            # Store in Redis
            self.r.xadd(
                "slam",
                {
                    "pose_x": 0.0,
                    "pose_y": 0.0,
                    "pose_z": 0.0,
                    "lat": str(lat),
                    "lon": str(lon),
                    "alt": str(alt),
                },
            )

            response = {
                "status": "success",
                "gps": {"lat": lat, "lon": lon, "alt": alt},
            }
        elif slam_status == "initializing":
            response = {
                "status": "initializing",
                "gps": {"lat": -1.0, "lon": -1.0, "alt": -1.0},
            }
        elif slam_status == "lost":
            response = {
                "status": "lost",
                "gps": {"lat": -3.0, "lon": -3.0, "alt": -3.0},
            }
        else:
            response = {
                "status": "error",
                "message": "Failed to process image or get GPS coordinates",
            }

        result.payload = json.dumps(response).encode(encoding="utf-8")
        result_wrapper.results.append(result)

        # Add control plane response
        response = control_plane.Response()
        response.seq_num = extras.cpt_request.seq_num
        response.timestamp.GetCurrentTime()
        response.resp = common.ResponseStatus.OK
        result_wrapper.extras.Pack(response)

        # Update timing stats
        self.count += 1
        if time.time() - self.lastprint > 5:
            self.print_inference_stats()
            self.lastprint = time.time()

        return result_wrapper

    def text_payload_reply(self):
        # status = gabriel_pb2.ResultWrapper.Status.SUCCESS
        status = gabriel_pb2.ResultWrapper.Status.WRONG_INPUT_FORMAT
        result_wrapper = self.get_result_wrapper(status)

        result = gabriel_pb2.ResultWrapper.Result()
        result.payload_type = gabriel_pb2.PayloadType.TEXT
        result.payload = b"Ignoring TEXT payload."
        result_wrapper.results.append(result)
        return result_wrapper

    def get_result_wrapper(self, status):
        result_wrapper = cognitive_engine.create_result_wrapper(status)
        result_wrapper.result_producer_name.value = self.ENGINE_NAME
        return result_wrapper

    def print_inference_stats(self):
        current_time = time.time()
        logger.info(f"inference time {(current_time - self.lasttime) * 1000:.1f} ms, ")
        logger.info(f"fps {1.0 / (current_time - self.lasttime):.2f}")
        logger.info(
            f"avg fps: {(self.count - self.lastcount) / (current_time - self.lastprint):.2f}"
        )
        self.lastcount = self.count
        self.lasttime = current_time
