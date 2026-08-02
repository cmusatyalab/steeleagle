#!/usr/bin/env python3

# Copyright (C) 2022 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import argparse
import datetime
import logging
import os
import signal
import time
from io import BytesIO

import cv2
import foxglove
import google.protobuf.json_format as json_format
import numpy as np
import pytz
import redis
from foxglove.schemas import CompressedImage, LocationFix
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine, local_engine
from PIL import Image
from steeleagle_protocol.v1.common import common_pb2
from steeleagle_protocol.v1.messages.telemetry import telemetry_pb2 as telemetry

logger = logging.getLogger(__name__)


class TelemetryEngine(cognitive_engine.Engine):
    ENGINE_NAME = "telemetry"

    def __init__(self, args):
        logger.info("Telemetry engine initializing...")
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
            f"{self.storage_path}/backend_{now.strftime('%d-%b-%Y-%H-%M-%S')}.mcap"
        )
        self.fg_server = foxglove.start_server(name="SteelEagle", host="0.0.0.0")

    def cleanup(self, signum, frame):
        logger.info("Stopping WS server and flushing MCAP file...")
        self.fg_server.stop()
        self.mcap.close()

    """
    Stores vehicle data in Redis. Less volatile data is stored in a HASH set, while
    frequently updated data is stored in a STREAM.
    """

    def updateVehicle(self, vehicle_id, extras, model=""):
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
        foxglove.log(
            f"/{vehicle_id}/telemetry",
            json_format.MessageToJson(
                extras,
                always_print_fields_with_no_presence=True,
            ),
            log_time=time.time_ns(),
        )

        vehicle_key = f"vehicle:{vehicle_id}"
        self.r.hset(vehicle_key, "last_seen", f"{time.time()}")
        if model:
            self.r.hset(vehicle_key, "model", model)
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
    Processes an input frame from Gabriel. For telemetry payloads,
    it updates the vehicle's tables in Redis. For imagery payloads,
    it writes the images to disk.
    """

    def handle(self, input_frame, client_info):
        logger.info("Processing incoming input frame from Gabriel...")

        status = gabriel_pb2.Status()

        vehicle_info = common_pb2.VehicleInfo()
        client_info.Unpack(vehicle_info)
        vehicle_id = vehicle_info.vehicle_id
        if vehicle_id == "":
            status.code = gabriel_pb2.StatusCode.ENGINE_ERROR
            status.message = "Client did not register a vehicle id"
            return cognitive_engine.Result(status, None)

        if input_frame.payload_type == gabriel_pb2.PayloadType.TEXT:
            tel = telemetry.Telemetry()
            assert input_frame.WhichOneof("payload") == "any_payload"
            assert input_frame.any_payload.Is(telemetry.Telemetry.DESCRIPTOR)
            input_frame.any_payload.Unpack(tel)

            logger.info(vehicle_id)
            self.updateVehicle(vehicle_id, tel, vehicle_info.model)
            return cognitive_engine.Result(status, "Telemetry updated")

        if input_frame.payload_type == gabriel_pb2.PayloadType.IMAGE:
            frame = telemetry.EncodedFrame()
            assert input_frame.WhichOneof("payload") == "any_payload"
            assert input_frame.any_payload.Is(telemetry.EncodedFrame.DESCRIPTOR)
            input_frame.any_payload.Unpack(frame)
            image_np = np.frombuffer(frame.encoded_data, dtype=np.uint8)

            # have redis publish the latest image
            if self.publish:
                logger.info(
                    f"Publishing image to redis under imagery.{vehicle_id} topic."
                )
                self.r.publish(f"imagery.{vehicle_id}", frame.encoded_data)
            # store images in the shared volume
            try:
                img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
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
                    logger.debug(
                        f"Directory {current_path} already exists. Moving on..."
                    )
                img.save(
                    f"{current_path}/{now.strftime('%H%M.%S%f')}.jpg", format="JPEG"
                )

                img.save(f"{vehicle_raw_dir}/temp.jpg", format="JPEG")
                os.rename(
                    f"{vehicle_raw_dir}/temp.jpg", f"{vehicle_raw_dir}/latest.jpg"
                )
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
                return cognitive_engine.Result(status, "Telemetry updated")
            except Exception as e:
                logger.error(f"Exception trying to store imagery: {e}")
                status.code = gabriel_pb2.StatusCode.ENGINE_ERROR
                status.message = str(e)
                return cognitive_engine.Result(status, None)

        logger.error(f"Engine received wrong input format: {input_frame.payload_type}")
        status.code = gabriel_pb2.StatusCode.WRONG_INPUT_FORMAT
        status.message = (
            f"Engine received wrong input format: {input_frame.payload_type}"
        )
        return cognitive_engine.Result(status, None)


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


def main():
    """Starts the Gabriel server."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("-p", "--port", type=int, default=9099, help="Set port number")

    parser.add_argument(
        "-g",
        "--gabriel",
        default="gabriel-server:5555",
        help="Gabriel server endpoint.",
    )

    parser.add_argument(
        "-r",
        "--redis",
        type=int,
        default=6379,
        help="Set port number for redis connection [default: 6379]",
    )

    parser.add_argument("-a", "--auth", default="", help="Share key for redis user.")

    parser.add_argument(
        "-l", "--publish", action="store_true", help="Publish incoming images via redis"
    )

    parser.add_argument(
        "-t",
        "--ttl",
        type=int,
        default=7,
        help="TTL in days before drones status tables are cleaned up in redis [default: 7]",
    )

    parser.add_argument(
        "--unittest",
        action="store_true",
        default=False,
        help="When enabled, will not connect to redis nor store images to disk.",
    )

    args, _ = parser.parse_known_args()

    def engine_factory():
        return TelemetryEngine(args)

    engine = local_engine.LocalEngine(
        engine_factory,
        input_queue_maxsize=60,
        port=args.port,
        num_tokens=2,
        engine_id="telemetry",
        use_zeromq=True,
    )

    engine.run()


if __name__ == "__main__":
    main()
