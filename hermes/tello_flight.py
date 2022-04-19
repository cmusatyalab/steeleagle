#!/usr/bin/env python3

# Copyright 2021 Carnegie Mellon University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from drones import utils
import time

if __name__ == "__main__":
    drone = utils.get_drone('dji')
    drone.connect()
    drone.takeOff()
    time.sleep(2)
    drone.moveBy(3, 0, 0)
    time.sleep(3)
    drone.moveBy(0, -3, 0)
    time.sleep(3)
    drone.moveBy(-3, 0, 0)
    time.sleep(3)
    drone.moveBy(0, 3, 0)
    time.sleep(3)
    drone.land()
    drone.disconnect()
