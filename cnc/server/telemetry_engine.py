#!/usr/bin/env python3

# Copyright (C) 2022 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import datetime
import logging
import os
import time

import cv2
import numpy as np
import redis
from cnc_protocol import cnc_pb2
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine
from PIL import Image

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class TelemetryEngine(cognitive_engine.Engine):
    ENGINE_NAME = "telemetry"

    def __init__(self, args):
        logger.info("Telemetry engine intializing...")

        self.r = redis.Redis(host='redis', port=args.redis, username='steeleagle', password=f'{args.auth}',decode_responses=True)
        self.r.ping()
        logger.info(f"Connected to redis on port {args.redis}...")
        self.storage_path = os.getcwd()+"/images/"
        try:
            os.makedirs(self.storage_path+"/raw")
        except FileExistsError:
            logger.info("Images directory already exists.")
        logger.info(f"Storing detection images at {self.storage_path}")
        self.current_path = None
        self.publish = args.publish

    def updateDroneStatus(self, extras):
        key = self.r.xadd(
                    f"telemetry.{extras.drone_id}",
                    {"latitude": extras.location.latitude, "longitude": extras.location.longitude, "altitude": extras.location.altitude,
                     "rssi": extras.status.rssi, "battery": extras.status.battery, "mag": extras.status.mag, "bearing": int(extras.status.bearing)},
                )
        logger.debug(f"Updated status of {extras.drone_id} in redis under stream telemetry at key {key}")

    def handle(self, input_frame):
        extras = cognitive_engine.unpack_extras(cnc_pb2.Extras, input_frame)

        status = gabriel_pb2.ResultWrapper.Status.SUCCESS
        result_wrapper = cognitive_engine.create_result_wrapper(status)
        result_wrapper.result_producer_name.value = self.ENGINE_NAME

        result = None
        
        if input_frame.payload_type == gabriel_pb2.PayloadType.TEXT:
            if extras.drone_id is not "":
                if extras.registering:
                    logger.info(f"Drone [{extras.drone_id}] connected.")
                    if not os.path.exists(f"{self.storage_path}/raw/{extras.drone_id}"):
                        os.mkdir(f"{self.storage_path}/raw/{extras.drone_id}")
                    self.current_path = f"{self.storage_path}/raw/{extras.drone_id}/{datetime.datetime.now().strftime('%d-%b-%Y-%H%M')}"
                    try:
                        os.mkdir(self.current_path)
                    except FileExistsError:
                        logger.error(f"Directory {self.current_path} already exists. Moving on....")

                result = gabriel_pb2.ResultWrapper.Result()
                result.payload_type = gabriel_pb2.PayloadType.TEXT
                result.payload = b"Telemetry updated."
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
                img.save(f"{self.storage_path}/raw/{extras.drone_id}/temp.jpg", format="JPEG")
                os.rename(f"{self.storage_path}/raw/{extras.drone_id}/temp.jpg", f"{self.storage_path}/raw/{extras.drone_id}/latest.jpg")
                logger.info(f"Updated {self.storage_path}/raw/{extras.drone_id}/latest.jpg")
            except Exception as e:
                logger.error(f"Exception trying to store imagery: {e}")
        
        # only append the result if it has a payload
        # e.g. in the elif block where we received an image from the streaming thread, we don't add a payload
        if result is not None:
            result_wrapper.results.append(result)
        return result_wrapper

