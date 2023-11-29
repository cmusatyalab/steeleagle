# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

from interfaces.FlightScript import FlightScript
# Import derived tasks
from task_defs.DetectTask import DetectTask
from task_defs.SetHome import SetHome

class MS(FlightScript):
   
    def __init__(self, drone, cloudlet):
        super().__init__(drone, cloudlet)
 
    def run(self):
        try:
            kwargs = {}
            # Polygon 1/DetectTask START
            kwargs.clear()
            kwargs["gimbal_pitch"] = "-45.0"
            kwargs["drone_rotation"] = "0.0"
            kwargs["sample_rate"] = "2"
            kwargs["hover_delay"] = "0"
            kwargs["model"] = "coco"
            kwargs["coords"] = "[{'lng': -79.9503848, 'lat': 40.4155378, 'alt': 25.0}, {'lng': -79.9502292, 'lat': 40.4155031, 'alt': 25.0}, {'lng': -79.9500777, 'lat': 40.4156849, 'alt': 25.0}, {'lng': -79.9502386, 'lat': 40.4157267, 'alt': 25.0}, {'lng': -79.9503848, 'lat': 40.4155378, 'alt': 25.0}]"
            t = DetectTask(self.drone, self.cloudlet, **kwargs)
            self.taskQueue.put(t)
            print("Added task DetectTask to the queue")
            # Point 3/SetHome START
            kwargs.clear()
            kwargs["coords"] = "[{'lng': -79.9499174, 'lat': 40.4158897, 'alt': 25.0}]"
            t = SetHome(self.drone, self.cloudlet, **kwargs)
            self.taskQueue.put(t)
            print("Added task SetHome to the queue")
            
            self.drone.takeOff()
            self._execLoop()
        except Exception as e:
            print(e)