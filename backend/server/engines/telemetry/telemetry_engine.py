#!/usr/bin/env python3

# Copyright (C) 2022 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import datetime
import logging
import os
import signal
import time
import cv2
import foxglove
import google.protobuf.json_format as json_format
import numpy as np
import pytz
import redis
from foxglove.schemas import CompressedImage, LocationFix
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine
from PIL import Image

from steeleagle_sdk.protocol.messages import telemetry_pb2 as telemetry

logger = logging.getLogger(__name__)
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logger.setLevel(getattr(logging, log_level, logging.INFO))


class TelemetryEngine(cognitive_engine.Engine):
    ENGINE_NAME = "telemetry"

    def __init__(self, args):
        logger.info("Telemetry engine intializing...")
        signal.signal(signal.SIGTERM, self.cleanup)
        # Connect to Redis database
        self.r = redis.Redis(
            host="redis",
            port=args.redis,
            username="steeleagle",
            password=f"{args.auth}",
            decode_responses=True,
        )
        self.r.ping()
        logger.info(f"Connected to redis on port {args.redis}...")

        self.storage_path = os.getcwd() + "/images/"
        try:
            os.makedirs(self.storage_path + "/raw")
        except FileExistsError:
            logger.info("Images directory already exists.")
        logger.info(f"Storing detection images at {self.storage_path}")

        self.publish = args.publish
        self.ttl_secs = args.ttl * 24 * 3600
        now = datetime.datetime.now(pytz.timezone("America/New_York"))
        self.mcap = foxglove.open_mcap(
            f"{self.storage_path}/backend_{now.strftime('%d-%b-%Y-%H-%M')}.mcap"
        )
        self.fg_server = foxglove.start_server(name="SteelEagle", host="0.0.0.0")

    def cleanup(self, signum, frame):
        logger.info("Stopping WS server and flushing MCAP file...")
        self.fg_server.stop()
        self.mcap.close()

    def updateDroneStatus(self, extras):
        global_pos = extras.global_position
        rel_pos = extras.relative_position
        body_vel = extras.velocity_body
        enu_vel = extras.velocity_enu
        gimb_pose = extras.gimbal_pose
        vehicle_info = extras.vehicle_info
        alert_info = extras.alert_info
        
        key = self.r.xadd(
            f"telemetry:{extras.vehicle_info.name}",
            {
                "latitude": global_pos.latitude,
                "longitude": global_pos.longitude,
                "abs_altitude": global_pos.altitude,
                "rel_altitude": rel_pos.up,
                "bearing": int(global_pos.heading),
                "battery": vehicle_info.battery_info.percentage,
                "mag": alert_info.magnetometer_warning,
                "sats": vehicle_info.gps_info.satellites,
                # Relative Pos (ENU)
                "enu_east": rel_pos.east,
                "enu_north": rel_pos.north,
                "enu_up": rel_pos.up,
                "enu_angle": rel_pos.angle,
                # Velocity Body
                "v_body_total": np.sqrt(
                    np.sum(
                        np.power(
                            [body_vel.forward_vel, body_vel.right_vel, body_vel.up_vel],
                            2,
                        )
                    )
                ),
                "v_body_forward": body_vel.forward_vel,
                "v_body_lateral": body_vel.right_vel,
                "v_body_altitude": body_vel.up_vel,
                "v_body_angular": body_vel.angular_vel,
                # Velocity ENU
                "v_enu_total": np.sqrt(
                    np.sum(
                        np.power(
                            [enu_vel.north_vel, enu_vel.east_vel, enu_vel.up_vel], 2
                        )
                    )
                ),
                "v_enu_north": enu_vel.north_vel,
                "v_enu_east": enu_vel.east_vel,
                "v_enu_up": enu_vel.up_vel,
                "v_enu_angular": enu_vel.angular_vel,
                # Gimbal Pose
                "gimbal_pitch": gimb_pose.pitch,
                "gimbal_roll": gimb_pose.roll,
                "gimbal_yaw": gimb_pose.yaw,
            },
        )
        self.r.expire(f"telemetry:{extras.vehicle_info.name}", 60 * 60 * 24)
        logger.debug(
            f"Updated status of {extras.vehicle_info.name} in redis under stream telemetry at key {key}"
        )

        drone_key = f"drone:{extras.vehicle_info.name}"
        self.r.hset(drone_key, "last_seen", f"{time.time()}")
        self.r.hset(drone_key, "battery", f"{extras.alert_info.battery_warning}")
        self.r.hset(drone_key, "mag", f"{extras.alert_info.magnetometer_warning}")
        self.r.hset(drone_key, "sats", f"{extras.alert_info.gps_warning}")
        self.r.hset(drone_key, "connection", f"{extras.alert_info.connection_warning}")
        self.r.hset(drone_key, "model", f"{extras.vehicle_info.model}")
        # Home Location
        self.r.hset(drone_key, "position_info.home_lat", f"{extras.position_info.home.latitude}")
        self.r.hset(drone_key, "position_info.home_long", f"{extras.position_info.home.longitude}")
        self.r.hset(drone_key, "position_info.home_alt", f"{extras.position_info.home.altitude}")
        # Camera Information
        self.r.hset(
            drone_key,
            "streams_allowed",
            f"{extras.imaging_sensor_info.stream_status.stream_capacity}",
        )
        self.r.hset(
            drone_key,
            "streams_active",
            f"{extras.imaging_sensor_info.stream_status.num_streams}",
        )
        self.r.hset(
            drone_key,
            "primary_cam_id",
            f"{extras.imaging_sensor_info.stream_status.primary_cam}",
        )
        for i in range(len(extras.imaging_sensor_info.stream_status.secondary_cams)):
            self.r.hset(drone_key, f"cam_{i}_id", f"{extras.imaging_sensor_info.sensors[i].id}")
            self.r.hset(
                drone_key,
                f"cam_{i}_type",
                f"{extras.imaging_sensor_info.sensors[i].type}",
            )
            self.r.hset(
                drone_key, f"cam_{i}_active", f"{extras.imaging_sensor_info.sensors[i].active}"
            )
            self.r.hset(
                drone_key,
                f"cam_{i}_support_sec",
                f"{extras.imaging_sensor_info.sensors[i].supports_secondary}",
            )

        self.r.expire(drone_key, self.ttl_secs)
        logger.debug(f"Updating {drone_key} status: last_seen: {time.time()}")

    def handle(self, input_frame):
        status = gabriel_pb2.ResultWrapper.Status.SUCCESS
        result_wrapper = cognitive_engine.create_result_wrapper(status)
        result_wrapper.result_producer_name.value = self.ENGINE_NAME
        result = None

        if input_frame.payload_type == gabriel_pb2.PayloadType.TEXT:
            extras = cognitive_engine.unpack_extras(telemetry.DriverTelemetry, input_frame)
            if extras.vehicle_info.name != "":
                result = gabriel_pb2.ResultWrapper.Result()
                result.payload_type = gabriel_pb2.PayloadType.TEXT
                result.payload = b"Telemetry updated."
                self.updateDroneStatus(extras)

        elif input_frame.payload_type == gabriel_pb2.PayloadType.IMAGE:
            extras = cognitive_engine.unpack_extras(telemetry.Frame, input_frame)
            image_np = np.fromstring(input_frame.payloads[0], dtype=np.uint8)
            # have redis publish the latest image
            if self.publish:
                logger.info(
                    f"Publishing image to redis under imagery.{extras.vehicle_info.name} topic."
                )
                self.r.publish(
                    f"imagery.{extras.vehicle_info.name}", input_frame.payloads[0]
                )
            # store images in the shared volume
            try:
                img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(img)

                drone_raw_dir = f"{self.storage_path}/raw/{extras.vehicle_info.name}"
                if not os.path.exists(drone_raw_dir):
                    os.mkdir(drone_raw_dir)
                now = datetime.datetime.now(pytz.timezone("America/New_York"))
                current_path = f"{drone_raw_dir}/{now.strftime('%d-%b-%Y')}"
                try:
                    os.mkdir(current_path)
                except FileExistsError:
                    logger.debug(
                        f"Directory {current_path} already exists. Moving on..."
                    )
                img.save(
                    f"{current_path}/{now.strftime('%H%M.%S%f')}.jpg", format="JPEG"
                )

                drone_raw_dir = f"{self.storage_path}/raw/{extras.vehicle_info.name}"
                img.save(f"{drone_raw_dir}/temp.jpg", format="JPEG")
                os.rename(f"{drone_raw_dir}/temp.jpg", f"{drone_raw_dir}/latest.jpg")

                logger.debug(f"Updated latest image for {extras.vehicle_info.name}")
            except Exception as e:
                logger.error(f"Exception trying to store imagery: {e}")

        # only append the result if it has a payload
        # e.g. in the elif block where we received an image from the streaming thread, we don't add a payload
        if result is not None:
            result_wrapper.results.append(result)
        return result_wrapper
