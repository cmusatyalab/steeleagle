# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

#from interfaces.Task import Task
import ast
import json
from json import JSONDecodeError
from gabriel_protocol import gabriel_pb2
import time
import asyncio
import logging
from transition_defs.TimerTransition import TimerTransition
from interfaces.Task import Task

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

#class ObstacleTask(Task):
class AvoidTask(Task):

    def __init__(self, drone, cloudlet, task_id, trigger_event_queue, task_args):
        super().__init__(drone, cloudlet, task_id, trigger_event_queue, task_args)
        # PID controller parameters
        self.time_prev = None
        self.error_prev = 0
        self.pid_info = {"constants" : {"Kp": 0.1, "Ki": 0.001, "Kd": 0.2}, "saved" : {"I": 0.0}}
        self.speed = self.task_attributes["speed"]

    
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

    async def moveForwardAndAvoid(self, error):
        ts = round(time.time() * 1000)
        # Reset pid loop if we haven't seen a target for a second or this is
        # the first target we have seen.
        if self.time_prev is None or (ts - self.time_prev) > 1000:
            self.time_prev = ts - 1 # Do this to prevent a divide by zero error!
            self.error_prev = error

        # Control loop
        P = self.pid_info["constants"]["Kp"] * error
        I = self.pid_info["constants"]["Ki"] * (ts - self.time_prev)
        if error < 0:
            I *= -1
        self.pid_info["saved"]["I"] += self.clamp(I, -100.0, 100.0)
        D = self.pid_info["constants"]["Kd"] * (error - self.error_prev) / (ts - self.time_prev)
        
        roll = self.clamp(int(P + I + D), -100, 100)
        self.time_prev = ts
        self.error_prev = error
        
        await self.drone.PCMD(roll, self.speed, 0, 0)

    async def run(self):
        # init
        logger.info("[ObstacleTask] Started run")
        self.cloudlet.switchModel(self.task_attributes["model"])
        self.create_transition()
        
        # logger.info(f"**************Avoid Task {self.task_id}: hi this is avoid task {self.task_id}**************\n")
        # coords = ast.literal_eval(self.task_attributes["coords"])
        # await self.drone.setGimbalPose(0.0, 0.0, 0.0)
        # for dest in coords:
        #     lng = dest["lng"]
        #     lat = dest["lat"]
        #     alt = dest["alt"]
        #     logger.info(f"**************Avoid Task {self.task_id}: Move **************\n")
        #     logger.info(f"**************Avoid Task {self.task_id}: move to {lat}, {lng}, {alt}**************\n")
        #     await self.drone.moveTo(lat, lng, alt)
        #     await asyncio.sleep(1)
        #     # await asyncio.sleep(hover_delay)

        # logger.info(f"**************Avoid Task {self.task_id}: Done**************\n")
        # self._exit()

        # try:
        while True:
            result = self.cloudlet.getResults("obstacle-avoidance")
            offset = 0
            try:
                logger.info("[ObstacleTask] Getting results")
                logger.info(f"[ObstacleTask] result: {result}")
                if result is not None and result.payload_type == gabriel_pb2.TEXT:
                    json_string = result.payload.decode('utf-8')
                    json_data = json.loads(json_string)
                    logger.info("[ObstacleTask] Decoded results")
                    offset = json_data[0]['vector']
                    await self.moveForwardAndAvoid(offset)
            except JSONDecodeError as e:
                logger.error(f"[ObstacleTask]: Error decoding JSON")
            await asyncio.sleep(0.1)
        # except Exception as e:
        #     logger.info(f"[ObstacleTask] Task failed with exception {e}")
        #     await self.drone.hover()