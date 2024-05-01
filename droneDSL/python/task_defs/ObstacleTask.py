# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

from interfaces.Task import Task
import json
import time
import asyncio

class ObstacleTask(Task):

    def __init__(self, drone, cloudlet, **kwargs):
        super().__init__(drone, cloudlet, **kwargs)

        # PID controller parameters
        self.time_prev = None
        self.error_prev = 0
        self.pid_info = {"constants", {"Kp": 1.0, "Ki": 0.09, "Kd": 10.0}, "saved" : {"I": 0.0}}

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

    async def moveForwardAndAvoid(error):
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
        
        roll = self.clamp(P + I + D, -100, 100)
        self.time_prev = ts
        self.error_prev = error
        
        await self.drone.PCMD(roll, self.speed, 0, 0)

    async def run(self):
        self.drone.setGimbalPose(0.0, 0.0, 0.0)
        try:
            while True:
                res = self.cloudlet.getResults("obstacle-avoidance")
                offset = 0
                if res is not None:
                    offset = res['vector']
                await self.moveForwardAndAvoid(offset)
        except Exception as e:
            self.drone.hover()

