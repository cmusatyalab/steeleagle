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

    async def run(self):
        # TODO: To be implemented
        pass
