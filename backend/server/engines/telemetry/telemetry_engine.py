#!/usr/bin/env python3

# Copyright (C) 2022 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import time
import datetime
import logging
from gabriel_server import cognitive_engine
from gabriel_protocol import gabriel_pb2
import protocol.common_pb2 as common
import protocol.gabriel_extras_pb2 as gabriel_extras
import redis
import os
from PIL import Image
import cv2
import numpy as np
from util.utils import setup_logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class TelemetryEngine(cognitive_engine.Engine):
    ENGINE_NAME = "telemetry"

    def __init__(self, args):
        logger.info("Telemetry engine intializing...")

        # Connect to Redis database
        self.r = redis.Redis(
            host='redis', port=args.redis, username='steeleagle',
            password=f'{args.auth}', decode_responses=True)
        self.r.ping()
        logger.info(f"Connected to redis on port {args.redis}...")

        self.storage_path = os.getcwd() + "/images/"
        try:
            os.makedirs(self.storage_path + "/raw")
        except FileExistsError:
            logger.info("Images directory already exists.")
        logger.info("Storing detection images at {}".format(self.storage_path))

        self.current_path = None
        self.publish = args.publish

    def updateDroneStatus(self, extras):
        telemetry = extras.telemetry
        global_pos = telemetry.global_position
        key = self.r.xadd(
            f"telemetry.{extras.drone_id}",
            {
                "latitude": global_pos.latitude,
                "longitude": global_pos.longitude,
                "altitude": global_pos.absolute_altitude,
                "bearing": int(global_pos.heading),
                #"rssi": extras.status.rssi,
                "battery": telemetry.battery,
                "mag": common.MagnetometerWarning.Name(telemetry.alerts.magnetometer_warning)
            },
        )
        logger.debug(f"Updated status of {extras.drone_id} in redis under stream telemetry at key {key}")

    def handle(self, input_frame):
        extras = cognitive_engine.unpack_extras(gabriel_extras.Extras, input_frame)

        status = gabriel_pb2.ResultWrapper.Status.SUCCESS
        result_wrapper = cognitive_engine.create_result_wrapper(status)
        result_wrapper.result_producer_name.value = self.ENGINE_NAME

        result = None

        if input_frame.payload_type == gabriel_pb2.PayloadType.TEXT:
            if extras.drone_id != "":
                if extras.registering:
                    logger.info(f"Drone [{extras.drone_id}] connected.")
                    drone_raw_dir = f"{self.storage_path}/raw/{extras.drone_id}"
                    if not os.path.exists(drone_raw_dir):
                        os.mkdir(drone_raw_dir)
                    self.current_path = f"{drone_raw_dir}/{datetime.datetime.now().strftime('%d-%b-%Y-%H%M')}"
                    try:
                        os.mkdir(self.current_path)
                    except FileExistsError:
                        logger.error(f"Directory {self.current_path} already exists. Moving on...")

                result = gabriel_pb2.ResultWrapper.Result()
                result.payload_type = gabriel_pb2.PayloadType.TEXT
                result.payload = "Telemetry updated.".encode(encoding="utf-8")
                self.updateDroneStatus(extras)

        elif input_frame.payload_type == gabriel_pb2.PayloadType.IMAGE:
            image_np = np.fromstring(input_frame.payloads[0], dtype=np.uint8)
            #have redis publish the latest image
            if self.publish:
                logger.info(f"Publishing image to redis under imagery.{extras.drone_id} topic.")
                self.r.publish(f'imagery.{extras.drone_id}', input_frame.payloads[0])
            #store images in the shared volume
            try:
                img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(img)

                img.save(f"{self.current_path}/{str(int(time.time() * 1000))}.jpg", format="JPEG")
                drone_raw_dir = f"{self.storage_path}/raw/{extras.drone_id}"

                img.save(f"{drone_raw_dir}/temp.jpg", format="JPEG")
                os.rename(f"{drone_raw_dir}/temp.jpg", f"{drone_raw_dir}/latest.jpg")

                logger.info(f"Updated {drone_raw_dir}/latest.jpg")
            except Exception as e:
                logger.error(f"Exception trying to store imagery: {e}")

        # only append the result if it has a payload
        # e.g. in the elif block where we received an image from the streaming thread, we don't add a payload
        if result is not None:
            result_wrapper.results.append(result)
        return result_wrapper

