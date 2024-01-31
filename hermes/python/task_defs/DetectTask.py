# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

from interfaces.Task import Task
import time
import ast
import asyncio
import logging

logger = logging.getLogger()

class DetectTask(Task):

    def __init__(self, drone, cloudlet, **kwargs):
        super().__init__(drone, cloudlet, **kwargs)

    async def run(self):
        try:
            logger.debug('[DetectTask] Running task...')
            self.cloudlet.switchModel(self.kwargs["model"])
            coords = ast.literal_eval(self.kwargs["coords"])
            await self.drone.setGimbalPose(0.0, float(self.kwargs["gimbal_pitch"]), 0.0)
            hover_delay = int(self.kwargs["hover_delay"])
            for dest in coords:
                lng = dest["lng"]
                lat = dest["lat"]
                alt = dest["alt"]
                logger.debug(f'[DetectTask] Moving to coords: {lat}, {lng}, {alt}')
                await self.drone.moveTo(lat, lng, alt)
                await asyncio.sleep(hover_delay)
        except Exception as e:
            print(e)


