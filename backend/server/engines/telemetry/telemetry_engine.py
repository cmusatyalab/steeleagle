#!/usr/bin/env python3

# Copyright (C) 2022 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import datetime
import logging
import os
import time
from io import BytesIO

import cv2
import foxglove
import google.protobuf.json_format as json_format
import numpy as np
import pytz
import redis
from foxglove.schemas import CompressedImage, LocationFix
from PIL import Image
from steeleagle_protocol.v1.messages.telemetry import telemetry_pb2 as telemetry

logger = logging.getLogger(__name__)


# The full names of the payloads the engine takes, as the vehicle's producers
# name their inputs' types.
TELEMETRY_TYPE = telemetry.Telemetry.DESCRIPTOR.full_name
FRAME_TYPE = telemetry.EncodedFrame.DESCRIPTOR.full_name


class TelemetryEngine:
    def __init__(self, args):
        logger.info("Telemetry engine initializing...")
        # Connect to Redis database
        self.r = redis.Redis(
            host=args.redis_host,
            port=args.redis,
            username="steeleagle",
            password=f"{args.auth}",
            decode_responses=True,
        )
        self.r.ping()
        logger.info(f"Connected to redis on port {args.redis}...")

        self.storage_path = args.storage + "/"
        try:
            os.makedirs(self.storage_path + "/raw")
        except FileExistsError:
            logger.info("Images directory already exists.")
        logger.info(f"Storing detection images at {self.storage_path}")

        self.publish = args.publish
        self.ttl_secs = args.ttl * 24 * 3600
        now = datetime.datetime.now(pytz.timezone("America/New_York"))
        self.mcap = foxglove.open_mcap(
            f"{self.storage_path}/backend_{now.strftime('%d-%b-%Y-%H-%M-%S')}.mcap"
        )
        self.fg_server = foxglove.start_server(name="SteelEagle", host="0.0.0.0")

    def cleanup(self):
        logger.info("Stopping WS server and flushing MCAP file...")
        self.fg_server.stop()
        self.mcap.close()

    """
    Stores vehicle data in Redis. Less volatile data is stored in a HASH set, while
    frequently updated data is stored in a STREAM.
    """

    def updateVehicle(self, vehicle_id, extras):
        global_pos = extras.position_info.global_position
        rel_pos = extras.position_info.relative_position
        body_vel = extras.position_info.velocity_body
        neu_vel = extras.position_info.velocity_neu
        # gimb_pose = extras.gimbal_info.gimbals[
        #    0
        # ].pose_body  # TODO: Change this to check if gimbal exists
        alert_info = extras.alert_info

        key = self.r.xadd(
            f"telemetry:{vehicle_id}",
            {
                "latitude": global_pos.latitude,
                "longitude": global_pos.longitude,
                "abs_altitude": global_pos.altitude,
                "rel_altitude": rel_pos.z,
                "bearing": int(global_pos.heading),
                "battery": extras.battery_info.percentage,
                "mag": alert_info.magnetometer_warning,
                "sats": extras.gps_info.satellites,
                # Relative Pos (ENU)
                "neu_east": rel_pos.y,
                "neu_north": rel_pos.x,
                "neu_up": rel_pos.z,
                "neu_angle": rel_pos.angle,
                # Velocity Body
                "v_body_total": np.sqrt(
                    np.sum(
                        np.power(
                            [body_vel.x_vel, body_vel.y_vel, body_vel.z_vel],
                            2,
                        )
                    )
                ),
                "v_body_forward": body_vel.x_vel,
                "v_body_lateral": body_vel.y_vel,
                "v_body_altitude": body_vel.z_vel,
                "v_body_angular": body_vel.angular_vel,
                # Velocity ENU
                "v_neu_total": np.sqrt(
                    np.sum(np.power([neu_vel.x_vel, neu_vel.y_vel, neu_vel.z_vel], 2))
                ),
                "v_neu_north": neu_vel.x_vel,
                "v_neu_east": neu_vel.y_vel,
                "v_neu_up": neu_vel.z_vel,
                "v_neu_angular": neu_vel.angular_vel,
                # Gimbal Pose
                # "gimbal_pitch": gimb_pose.pitch,
                # "gimbal_roll": gimb_pose.roll,
                # "gimbal_yaw": gimb_pose.yaw,
            },
        )
        self.r.expire(f"telemetry:{vehicle_id}", self.ttl_secs)
        logger.debug(
            f"Updated status of {vehicle_id} in redis under stream telemetry at key {key}"
        )
        foxglove.log(
            f"/{vehicle_id}/location",
            LocationFix(
                latitude=global_pos.latitude,
                longitude=global_pos.longitude,
                altitude=global_pos.altitude,
            ),
            log_time=time.time_ns(),
        )
        try:
            telemetry_json = json_format.MessageToJson(
                extras,
                always_print_fields_with_no_presence=True,
            )
        except TypeError as e:
            logger.warning(
                f"Could not serialize telemetry for {vehicle_id} to JSON, "
                f"likely an unrecognized Any payload in position_info.setpoint "
                f"or gimbal_info.gimbal_setpoint: {e}"
            )
            telemetry_json = None

        if telemetry_json is not None:
            foxglove.log(
                f"/{vehicle_id}/telemetry",
                telemetry_json,
                log_time=time.time_ns(),
            )

        vehicle_key = f"vehicle:{vehicle_id}"
        self.r.hset(vehicle_key, "last_seen", f"{time.time()}")
        # The GCS requires a model, but the vehicle no longer sends one, so
        # an unknown model is stored as empty.
        self.r.hsetnx(vehicle_key, "model", "")
        self.r.hset(vehicle_key, "battery", f"{extras.alert_info.battery_warning}")
        self.r.hset(vehicle_key, "mag", f"{extras.alert_info.magnetometer_warning}")
        self.r.hset(vehicle_key, "sats", f"{extras.alert_info.gps_warning}")
        self.r.hset(
            vehicle_key, "connection", f"{extras.alert_info.connection_warning}"
        )
        # Home Location
        self.r.hset(
            vehicle_key,
            "position_info.home_lat",
            f"{extras.position_info.home.latitude}",
        )
        self.r.hset(
            vehicle_key,
            "position_info.home_long",
            f"{extras.position_info.home.longitude}",
        )
        self.r.hset(
            vehicle_key,
            "position_info.home_alt",
            f"{extras.position_info.home.altitude}",
        )

        self.r.expire(vehicle_key, self.ttl_secs)
        logger.debug(f"Updating {vehicle_key} status: last_seen: {time.time()}")

    """
    Processes an input from Gabriel. For telemetry payloads, it updates the
    vehicle's tables in Redis. For imagery payloads, it writes the images to
    disk. The vehicle names its producers "<vehicle>.telemetry" and
    "<vehicle>.frames", so the producer's name gives the vehicle's id.
    """

    def handle(self, input):
        vehicle_id = input.id.producer.rpartition(".")[0]
        if vehicle_id == "":
            logger.error(f"Producer {input.id.producer} names no vehicle")
            return

        if input.payload_type == TELEMETRY_TYPE:
            tel = telemetry.Telemetry()
            tel.ParseFromString(bytes(input.data))
            logger.info(vehicle_id)
            self.updateVehicle(vehicle_id, tel)
            return

        if input.payload_type == FRAME_TYPE:
            frame = telemetry.EncodedFrame()
            frame.ParseFromString(bytes(input.data))
            self.storeFrame(vehicle_id, frame)
            return

        logger.error(f"Engine received wrong input format: {input.payload_type}")

    def storeFrame(self, vehicle_id, frame):
        image_np = np.frombuffer(frame.encoded_data, dtype=np.uint8)

        # have redis publish the latest image
        if self.publish:
            logger.info(f"Publishing image to redis under imagery.{vehicle_id} topic.")
            self.r.publish(f"imagery.{vehicle_id}", frame.encoded_data)
        # store images in the shared volume
        img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
        if img is None:
            logger.error(f"Could not decode a frame from {vehicle_id}")
            return
        add_watermark(img)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(img)

        vehicle_raw_dir = f"{self.storage_path}/raw/{vehicle_id}"
        os.makedirs(vehicle_raw_dir, exist_ok=True)
        now = datetime.datetime.now(pytz.timezone("America/New_York"))
        current_path = f"{vehicle_raw_dir}/{now.strftime('%d-%b-%Y')}"
        try:
            os.mkdir(current_path)
        except FileExistsError:
            logger.debug(f"Directory {current_path} already exists. Moving on...")
        img.save(f"{current_path}/{now.strftime('%H%M.%S%f')}.jpg", format="JPEG")

        img.save(f"{vehicle_raw_dir}/temp.jpg", format="JPEG")
        os.rename(f"{vehicle_raw_dir}/temp.jpg", f"{vehicle_raw_dir}/latest.jpg")
        resampled_out = BytesIO()
        img.thumbnail((320, 240), Image.LANCZOS)
        img.save(resampled_out, format="JPEG")
        thumbnail = resampled_out.getvalue()
        foxglove.log(
            f"/{vehicle_id}/imagery",
            CompressedImage(data=thumbnail, format="jpeg"),
            log_time=time.time_ns(),
        )
        logger.debug(f"Updated latest image for {vehicle_id}")


def add_watermark(img):
    ts = time.strftime("%H:%M:%S")
    cv2.putText(
        img, f"{ts}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 5, cv2.LINE_AA
    )
    cv2.putText(
        img,
        f"{ts}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
