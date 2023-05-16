#!/usr/bin/env python3

# Copyright (C) 2022 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import time
import validators
import numpy as np
import logging
from gabriel_server import cognitive_engine
from gabriel_protocol import gabriel_pb2
from cnc_protocol import cnc_pb2
from urllib.parse import urlparse
from io import BytesIO
import threading
from PIL import Image
import json
import cv2
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

drone_schema = {
    "type": "object",
    "properties": {
        "name": {
            "description": "Name of the drone",
            "type": "string",
        },
        "latitude": {
            "description": "The drone's current latitude",
            "type": "number",
            "minimum": -90.0,
            "maximum": 90.0
        },
        "longitude": {
            "description": "The drone's current longitude",
            "type": "number",
            "minimum": -180.0,
            "maximum": 180.0
        },
        "altitude": {
            "description": "The drone's current altitude",
            "type": "number",
            "minimum": 0.0,
        },
        "velocity": {
            "description": "The drone's current velocity",
            "type": "number",
            "minimum": 0.0,
        },
        "state": {
            "description": "The drone's status",
            "type": "string",
            "enum": ["offline", "online", "flying"],
            "default": "offline"
        },
    }
}


class DroneClient:
    def __init__(self, id, heartbeat):
        self.id = id
        self.heartbeat = heartbeat
        self.rth = self.sent_halt = self.takeoff = self.land = self.manual = False
        self.pitch = self.yaw = self.roll = self.gaz = 0
        self.script_url = ''
        self.lat = 0.0
        self.lon = 0.0
        self.alt = 0.0
        self.vel = 0.0
        self.battery = self.rssi = self.mag = self.bearing =  0
        self.current_frame = False
        self.json = {"name": id, "state": "online", "latitude": 0.0,
                     "longitude": 0.0, "altitude": 0.0, "velocity": 0.0, "battery": 0, "rssi": 0,
                     "mag": 0, "bearing": 0}


class DroneCommandEngine(cognitive_engine.Engine):
    ENGINE_NAME = "command"

    def __init__(self, args):
        logger.info("Drone command engine intializing...")
        self.drones = {}
        self.timeout = args.timeout
        self.store_images = args.store
        self.invalidator = threading.Thread(
            target=self.invalidateDrones, daemon=True)
        self.invalidator.start()

    def updateDroneStatus(self, extras):
        self.drones[extras.drone_id].json["latitude"] = self.drones[extras.drone_id].lat = extras.location.latitude
        self.drones[extras.drone_id].json["longitude"] = self.drones[extras.drone_id].lon = extras.location.longitude
        self.drones[extras.drone_id].json["altitude"] = self.drones[extras.drone_id].alt = extras.location.altitude
        self.drones[extras.drone_id].json["rssi"] = self.drones[extras.drone_id].rssi = extras.status.rssi
        self.drones[extras.drone_id].json["battery"] = self.drones[extras.drone_id].battery = extras.status.battery
        self.drones[extras.drone_id].json["mag"] = self.drones[extras.drone_id].mag = extras.status.mag
        self.drones[extras.drone_id].json["bearing"] = self.drones[extras.drone_id].bearing = int(extras.status.bearing)
        logger.debug(f"Updated {extras.drone_id} status to {self.drones[extras.drone_id].json}")

    def getDrones(self):
        all_drones = []
        for _, drone in self.drones.items():
            all_drones.append(drone.json)
        return json.dumps(all_drones)

    def invalidateDrones(self):
        ticks = 0
        while(True):
            if ticks % 10 == 0:
                logger.info(f"===Connected drones===")
                for key in self.drones.keys():
                    logger.info(f"  [{key}]")
            invalid = None
            for key, drone in self.drones.items():
                if (time.time() - drone.heartbeat) > self.timeout:
                    logger.info(
                        f"Haven't heard from drone [{drone.id}] in {self.timeout} seconds. Invalidating...")
                    invalid = key
            if invalid is not None:
                del self.drones[invalid]
            ticks = ticks + 1
            time.sleep(1)

    def handle(self, input_frame):
        extras = cognitive_engine.unpack_extras(cnc_pb2.Extras, input_frame)

        status = gabriel_pb2.ResultWrapper.Status.SUCCESS
        result_wrapper = cognitive_engine.create_result_wrapper(status)
        result_wrapper.result_producer_name.value = self.ENGINE_NAME

        result = gabriel_pb2.ResultWrapper.Result()
        result.payload_type = gabriel_pb2.PayloadType.TEXT

        # if it is a drone client...
        if extras.drone_id is not "":
            if extras.registering:
                d = DroneClient(extras.drone_id, time.time())
                # Add the drone to our list of connected drones
                self.drones[d.id] = d
                logger.info(f"Drone [{d.id}] connected.")
                result.payload = "Registration successful!".encode(
                    encoding="utf-8")
            else:
                try:
                    if input_frame.payload_type == gabriel_pb2.PayloadType.TEXT:
                        if extras.drone_id in self.drones:
                            self.drones[extras.drone_id].heartbeat = time.time()
                            self.updateDroneStatus(extras)
                            # check if there is a script to send or if we need to signal a halt
                            if self.drones[extras.drone_id].sent_halt:
                                from_commander = cnc_pb2.Extras()
                                from_commander.cmd.halt = True
                                result_wrapper.extras.Pack(from_commander)
                                result.payload = "!Halt sent!".encode(
                                    encoding="utf-8")
                                logger.debug(
                                    f'Instructing drone {extras.drone_id} to halt and enable manual control...')
                                self.drones[extras.drone_id].sent_halt = False
                            elif self.drones[extras.drone_id].script_url != '':
                                url = self.drones[extras.drone_id].script_url
                                from_commander = cnc_pb2.Extras()
                                if validators.url(url, public=True) == True:
                                    from_commander.cmd.script_url = url
                                    result_wrapper.extras.Pack(from_commander)
                                    result.payload = "Script URL sent.".encode(
                                        encoding="utf-8")
                                    logger.debug(
                                        f'Directing {extras.drone_id} to to run flight script at {url}...')
                                    self.drones[extras.drone_id].script_url = ''
                                else:
                                    logger.error(
                                        f"Invalid URL [{url}] given as flight script.")
                            elif self.drones[extras.drone_id].takeoff:
                                from_commander = cnc_pb2.Extras()
                                from_commander.cmd.takeoff = True
                                result_wrapper.extras.Pack(from_commander)
                                result.payload = "!Takeoff sent!".encode(
                                    encoding="utf-8")
                                logger.debug(
                                    f'Instructing drone {extras.drone_id} to takeoff...')
                                self.drones[extras.drone_id].takeoff = False
                            elif self.drones[extras.drone_id].land:
                                from_commander = cnc_pb2.Extras()
                                from_commander.cmd.land = True
                                result_wrapper.extras.Pack(from_commander)
                                result.payload = "!Land sent!".encode(
                                    encoding="utf-8")
                                logger.debug(
                                    f'Instructing drone {extras.drone_id} to land...')
                                self.drones[extras.drone_id].land = False
                            elif self.drones[extras.drone_id].rth:
                                from_commander = cnc_pb2.Extras()
                                from_commander.cmd.rth = True
                                result_wrapper.extras.Pack(from_commander)
                                result.payload = "!RTH sent!".encode(
                                    encoding="utf-8")
                                logger.debug(
                                    f'Instructing drone {extras.drone_id} to return-to-home...')
                                self.drones[extras.drone_id].rth = False
                            elif self.drones[extras.drone_id].manual:
                                from_commander = cnc_pb2.Extras()
                                from_commander.cmd.pcmd.gaz = self.drones[extras.drone_id].gaz
                                from_commander.cmd.pcmd.yaw = self.drones[extras.drone_id].yaw
                                from_commander.cmd.pcmd.pitch = self.drones[extras.drone_id].pitch
                                from_commander.cmd.pcmd.roll = self.drones[extras.drone_id].roll
                                result_wrapper.extras.Pack(from_commander)
                                result.payload = "Sending PCMD commands.".encode(
                                    encoding="utf-8")
                    elif input_frame.payload_type == gabriel_pb2.PayloadType.IMAGE:
                        #update current_frame for this drone so it can be displayed in commander UI
                        self.drones[extras.drone_id].current_frame = input_frame.payloads[0]
                except KeyError:
                    logger.error(
                        f'Sorry, drone [{extras.drone_id}]  has not registered yet!')
        # if it is a commander client...
        elif extras.commander_id is not "":
            commander = extras.commander_id
            try:
                drone = extras.cmd.for_drone_id
                payload = self.getDrones()
                result.payload = payload.encode(encoding="utf-8")
                result_wrapper.results.append(result)
                if extras.cmd.halt:
                    logger.info(
                        f'Commander [{commander}] requests a halt be sent to drone [{drone}].')
                    self.drones[drone].sent_halt = True
                elif extras.cmd.takeoff:
                    logger.info(
                        f'Commander [{commander}] requests that drone [{drone}] takeoff.')
                    self.drones[drone].takeoff = True
                elif extras.cmd.land:
                    logger.info(
                        f'Commander [{commander}] requests that drone [{drone}] land.')
                    self.drones[drone].land = True
                elif extras.cmd.rth:
                    logger.info(
                        f'Commander [{commander}] requests that drone [{drone}] return-to-home.')
                    self.drones[drone].rth = True
                elif extras.cmd.script_url is not "":
                    url = extras.cmd.script_url
                    if validators.url(url, public=True) == True:
                        logger.info(
                            f'Commander [{commander}] requests drone [{drone}] run flight script at {url}.')
                        self.drones[drone].script_url = url
                        self.drones[drone].manual = False
                    else:
                        logger.error(
                            f'Sorry, [{commander}]  {url} is invalid!')
                elif extras.cmd.manual:
                    self.drones[drone].manual = True
                    logger.debug(
                        f'Commander [{commander}] sent PCMD[{extras.cmd.pcmd.gaz},{extras.cmd.pcmd.yaw},{extras.cmd.pcmd.pitch},{extras.cmd.pcmd.roll}] for drone [{drone}].')
                    self.drones[drone].gaz = extras.cmd.pcmd.gaz
                    self.drones[drone].yaw = extras.cmd.pcmd.yaw
                    self.drones[drone].pitch = extras.cmd.pcmd.pitch
                    self.drones[drone].roll = extras.cmd.pcmd.roll

                if self.drones[drone].current_frame != False:
                    result = gabriel_pb2.ResultWrapper.Result()
                    result.payload_type = gabriel_pb2.PayloadType.IMAGE
                    result.payload = self.drones[drone].current_frame
            except KeyError:
                if drone != "":
                    logger.error(
                        f'Sorry, [{commander}]  drone [{drone}] does not exist!')
        result_wrapper.results.append(result)
        return result_wrapper

    def process_image(self, image):
        np_data = np.fromstring(image, dtype=np.uint8)
        img = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(img)

        return BytesIO(img)
