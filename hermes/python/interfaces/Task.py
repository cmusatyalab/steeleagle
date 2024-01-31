# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import asyncio
import ctypes
from abc import ABC, abstractmethod

class Task(ABC):

    def __init__(self, drone, cloudlet, **kwargs):
        self.drone = drone
        self.cloudlet = cloudlet
        self.kwargs = kwargs

    @abstractmethod
    async def run(self):
        pass

    def pause(self):
        pass

    def resume(self):
        pass
