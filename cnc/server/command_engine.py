#!/usr/bin/env python3
# CommandAndControl
#   - Platform Agnostic Automated Drone Control
#   Author: Thomas Eiszler <teiszler@andrew.cmu.edu>
#
#   Copyright (C) 2022 Carnegie Mellon University
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

import base64
import time
import os
import uuid
import validators
import numpy as np
import logging
from gabriel_server import cognitive_engine
from gabriel_protocol import gabriel_pb2
from cnc_protocol import cnc_pb2
import uuid
from urllib.parse import urlparse
from io import BytesIO
import threading
import jsonschema
import json

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

drone_schema = {
                    "type" : "object",
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
        self.sent_halt = False
        self.script_url = ''
        self.json = {"name" : id, "state": "online", "latitude": 0.0, "longitude": 0.0, "altitude" : 0.0, "velocity": 0.0}
    
class DroneCommandEngine(cognitive_engine.Engine):
    ENGINE_NAME = "command"

    def __init__(self, args):
        logger.info("Drone command engine intializing...")
        self.drones = {}
        self.timeout = args.timeout
        self.invalidator = threading.Thread(target=self.invalidateDrones, daemon=True)
        self.invalidator.start()

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
                    logger.info(f"Haven't heard from drone [{drone.id}] in {self.timeout} seconds. Invalidating...")
                    invalid = key
            if invalid is not None:
                del self.drones[invalid]
            ticks = ticks + 1
            time.sleep(1)

    def handle(self, input_frame):
        if input_frame.payload_type != gabriel_pb2.PayloadType.TEXT:
            status = gabriel_pb2.ResultWrapper.Status.WRONG_INPUT_FORMAT
            return cognitive_engine.create_result_wrapper(status)

        extras = cognitive_engine.unpack_extras(cnc_pb2.Extras, input_frame)

        status = gabriel_pb2.ResultWrapper.Status.SUCCESS
        result_wrapper = cognitive_engine.create_result_wrapper(status)
        result_wrapper.result_producer_name.value = self.ENGINE_NAME

        result = gabriel_pb2.ResultWrapper.Result()
        result.payload_type = gabriel_pb2.PayloadType.TEXT

        #if it is a drone client...
        if extras.drone_id is not "":
            if extras.registering:
                d = DroneClient(extras.drone_id, time.time())
                self.drones[d.id] = d #Add the drone to our list of connected drones
                logger.info(f"Drone [{d.id}] connected.")
                result.payload = "Registration successful!".encode(encoding="utf-8")
            else:
                try:
                    self.drones[extras.drone_id].heartbeat = time.time()
                    if extras.drone_id in self.drones:
                        #check if there is a script to send or if we need to signal a halt
                        if self.drones[extras.drone_id].sent_halt:
                            from_commander = cnc_pb2.Extras()
                            from_commander.cmd.halt = True
                            result_wrapper.extras.Pack(from_commander)
                            result.payload = "!Halt sent!".encode(encoding="utf-8")
                            logger.debug(f'Instructing drone {extras.drone_id} to halt and enable manual control...')
                            self.drones[extras.drone_id].sent_halt = False
                        elif self.drones[extras.drone_id].script_url != '':
                            url = self.drones[extras.drone_id].script_url
                            from_commander = cnc_pb2.Extras()
                            if validators.url(url, public=True) == True:
                                from_commander.cmd.script_url = url
                                result_wrapper.extras.Pack(from_commander)
                                result.payload = "Script URL sent.".encode(encoding="utf-8")
                                logger.debug(f'Directing {extras.drone_id} to to run flight script at {url}...')
                                self.drones[extras.drone_id].script_url = ''
                            else:
                                logger.error(f"Invalid URL [{url}] given as flight script.")
                        else:
                            result.payload = "No command.".encode(encoding="utf-8")
                except KeyError:
                    logger.error(f'Sorry, drone [{extras.drone_id}]  has not registered yet!')
        #if it is a commander client...
        elif extras.commander_id is not "":
            commander = extras.commander_id
            if extras.cmd is not "":
                try:
                    drone = extras.cmd.for_drone_id
                    if extras.cmd.halt:
                        logger.info(f'Commander [{commander}] requests a halt be sent to drone [{drone}].')
                        self.drones[drone].sent_halt = True
                        result.payload = f'Halt sent to drone {drone}.'.encode(encoding="utf-8")
                    elif extras.cmd.script_url is not "":
                        url = extras.cmd.script_url
                        if validators.url(url, public=True) == True:
                            logger.info(f'Commander [{commander}] requests drone [{drone}] run flight script at {url}.')
                            self.drones[drone].script_url = url
                            result.payload = f'Script URL sent to drone {drone}.'.encode(encoding="utf-8")
                        else:
                            logger.error(f'Sorry, [{commander}]  {url} is invalid!')
                            result.payload = f'Invalid URL sent {url}!'.encode(encoding="utf-8")
                    else:
                        #if there is no command
                        #return the list of connected drones to the commander
                        logger.info(f'Commander [{commander}] requests drone list.')
                        payload = self.getDrones()
                        result.payload = payload.encode(encoding="utf-8")
                except KeyError:
                    logger.error(f'Sorry, [{commander}]  drone [{drone}] does not exist!')
                    result.payload = f'Drone {drone} is not connected.'.encode(encoding="utf-8")

        result_wrapper.results.append(result)
        return result_wrapper

    def preprocess_image(self, image):
        return BytesIO(image)



