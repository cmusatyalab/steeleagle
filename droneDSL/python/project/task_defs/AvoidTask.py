# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

#from interfaces.Task import Task
import json
from json import JSONDecodeError
import time
import asyncio
import logging
from gabriel_protocol import gabriel_pb2
from ..transition_defs.TimerTransition import TimerTransition
from interface.Task import Task

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class AvoidTask(Task):
        

    def __init__(self, drone, cloudlet, task_id, trigger_event_queue, task_args):
        super().__init__(drone, cloudlet, task_id, trigger_event_queue, task_args)
        self.drone = drone
        self.cloudlet = cloudlet

        # PID controller parameters
        self.time_prev = None
        self.error_prev = 0
        self.setpt = [0.0, 0.0]
        self.roll_pid_info = {"constants" : {"Kp": 5.0, "Ki": 0.01, "Kd": 6.0}, "saved" : {"I": 0.0}}
        self.pitch_pid_info = {"constants" : {"Kp": 5.0, "Ki": 0.01, "Kd": 6.0}, "saved" : {"I": 0.0}}
        self.forwardspeed = 1.5 
        self.horizontalspeed = 1
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
        fspeed = speeds["speedX"]
        hspeed = speeds["speedY"]
        logger.info(f"[ObstacleTask] HSpeed: {hspeed}, FSpeed: {fspeed}")
        return [self.setpt[0] - hspeed, self.setpt[1] - fspeed]

    async def moveForwardAndAvoid(self, error):
        ts = round(time.time() * 1000)
        if self.time_prev is None or (ts - self.time_prev) > 1000:
            self.time_prev = ts - 1 # Do this to prevent a divide by zero error!
            self.error_prev = error

        # Roll control loop
        Pr = self.roll_pid_info["constants"]["Kp"] * error[0]
        Ir = self.roll_pid_info["constants"]["Ki"] * (ts - self.time_prev)
        if error[0] < 0:
            Ir *= -1
        if error[0] == 0:
            self.roll_pid_info["saved"]["I"] = 0
        else:
            self.roll_pid_info["saved"]["I"] += self.clamp(Ir, -100.0, 100.0)
        Dr = self.roll_pid_info["constants"]["Kd"] * (error[0] - self.error_prev[0]) / (ts - self.time_prev)
        
        roll = self.clamp(int(Pr + Ir + Dr), -100, 100)
        
        # Pitch control loop
        Pp = self.pitch_pid_info["constants"]["Kp"] * error[1]
        Ip = self.pitch_pid_info["constants"]["Ki"] * (ts - self.time_prev)
        if error[1] < 0:
            Ip *= -1
        if error[1] == 0:
            self.pitch_pid_info["saved"]["I"] = 0
        else:
            self.pitch_pid_info["saved"]["I"] += self.clamp(Ip, -100.0, 100.0)
        Dp = self.pitch_pid_info["constants"]["Kd"] * (error[1] - self.error_prev[1]) / (ts - self.time_prev)
        
        pitch = self.clamp(int(Pp + Ip + Dp), -100, 100)

        self.time_prev = ts
        self.error_prev = error

        logger.info(f"[ObstacleTask] Giving PCMD {roll} {pitch}")
        await self.drone.PCMD(roll, pitch, 0, 0)

    def setPoint(self, error):
        # Calculate horizontal error
        newpt = error * self.horizontalspeed
        if newpt * self.setpt[0] < 0 and abs(self.setpt[0] - newpt) > 0.5 and self.oscillations < 3: # Check if they have different signs
            self.oscillations += 1 
        else:
            self.oscillations = 0
            self.setpt[0] = error * self.horizontalspeed
        # Calculate forward error
        if abs(error) >= 0.1:
            self.setpt[1] = 0
        else:
            self.setpt[1] = self.forwardspeed

    @Task.call_after_exit
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

