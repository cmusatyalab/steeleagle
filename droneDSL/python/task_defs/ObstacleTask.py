# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

#from interfaces.Task import Task
import json
from json import JSONDecodeError
from gabriel_protocol import gabriel_pb2
import time
import asyncio
import logging
import math

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class ObstacleTask(Task):

    def __init__(self, drone, cloudlet, **kwargs):
        #super().__init__(drone, cloudlet, **kwargs)
        self.drone = drone
        self.cloudlet = cloudlet

        # PID controller parameters
        self.time_prev = None
        self.error_prev = 0
        self.setpt = 0.0
        self.pid_info = {"constants" : {"Kp": 3.0, "Ki": 0.01, "Kd": 4.0}, "saved" : {"I": 0.0}}
        self.forwardspeed = 15
        self.horizontalspeed = 2
        self.oscillations = 0

    def create_transition(self):
        logger.info(self.transitions_attributes)
        args = {
            'task_id': self.task_id,
            'trans_active': self.trans_active,
            'trans_active_lock': self.trans_active_lock,
            'trigger_event_queue': self.trigger_event_queue
        }
        
        # Triggered event
        if ("timeout" in self.transitions_attributes):
            timer = TimerTransition(args, self.transitions_attributes["timeout"])
            timer.daemon = True
            timer.start()

    def clamp(self, value, minimum, maximum):
        return max(minimum, min(value, maximum))

    async def computeError(self):
        speeds = await self.drone.getSpeedRel()
        hspeed = speeds["speedY"]
        logger.info(f"[ObstacleTask] HSpeed: {hspeed}")
        return self.setpt - hspeed 

    async def moveForwardAndAvoid(self, error):
        ts = round(time.time() * 1000)
        if self.time_prev is None or (ts - self.time_prev) > 1000:
            self.time_prev = ts - 1 # Do this to prevent a divide by zero error!
            self.error_prev = error

        # Control loop
        P = self.pid_info["constants"]["Kp"] * error
        I = self.pid_info["constants"]["Ki"] * (ts - self.time_prev)
        if error < 0:
            I *= -1
        if error == 0:
            self.pid_info["saved"]["I"] = 0
        else:
            self.pid_info["saved"]["I"] += self.clamp(I, -100.0, 100.0)
        D = self.pid_info["constants"]["Kd"] * (error - self.error_prev) / (ts - self.time_prev)
        
        roll = self.clamp(int(P + I + D), -100, 100)
        self.time_prev = ts
        self.error_prev = error

        pitch = self.forwardspeed
        if abs(error) >= 0.4:
            pitch = int(self.forwardspeed / 4)
            
        logger.info(f"[ObstacleTask] Giving PCMD {roll} {pitch}")
        await self.drone.PCMD(roll, pitch, 0, 0)

    def setPoint(self, error):
        newpt = error * self.horizontalspeed
        if newpt * self.setpt < 0 and abs(self.setpt - newpt) > 0.5 and self.oscillations < 3: # Check if they have different signs
            self.oscillations += 1 
        else:
            self.oscillations = 0
            self.setpt = error * self.horizontalspeed

    async def run(self):
        logger.info("[ObstacleTask] Started run")
        await self.drone.setGimbalPose(0.0, 0.0, 0.0)
        try:
            while True:
                result = self.cloudlet.getResults("obstacle-avoidance")
                offset = 0
                try:
                    logger.info(f"[ObstacleTask] result: {result}")
                    if result is not None and result.payload_type == gabriel_pb2.TEXT:
                        json_string = result.payload.decode('utf-8')
                        json_data = json.loads(json_string)
                        logger.info("[ObstacleTask] Decoded results")
                        offset = json_data[0]['vector']
                        self.setPoint(offset)
                    logger.info(f"[ObstacleTask] Set point {self.setpt}")
                    error = await self.computeError()
                    logger.info(f"[ObstacleTask] Error {error}")
                    await self.moveForwardAndAvoid(error)
                except JSONDecodeError as e:
                    logger.error(f"[ObstacleTask]: Error decoding JSON")
                except Exception as e:
                    logger.error(f"[ObstacleTask] Threw an exception")
                    logger.error(e)
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.info(f"[ObstacleTask] Task failed with exception {e}")
            await self.drone.hover()
        self._exit()

