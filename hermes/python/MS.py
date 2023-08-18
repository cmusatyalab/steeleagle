from interfaces.FlightScript import FlightScript
import threading
# Import derived tasks
from task_defs.DetectTask import DetectTask

class MS(FlightScript, threading.Thread):
   
    def __init__(self, drone, cloudlet):
        threading.Thread.__init__(self)
        super().__init__(drone, cloudlet)
 
    def run(self):
        try:
            kwargs = {}
            # Detect/DetectTask START
            kwargs.clear()
            kwargs["gimbal_pitch"] = "-45.0"
            kwargs["drone_rotation"] = "0.0"
            kwargs["sample_rate"] = "2"
            kwargs["hover_delay"] = "5"
            kwargs["model"] = "coco"
            kwargs["coords"] = "[{'lng': -79.9504203, 'lat': 40.4158615, 'alt': 15.0}, {'lng': -79.9504431, 'lat': 40.4157931, 'alt': 15.0}, {'lng': -79.9502553, 'lat': 40.4157349, 'alt': 15.0}, {'lng': -79.9501494, 'lat': 40.4158717, 'alt': 15.0}, {'lng': -79.9503492, 'lat': 40.4159544, 'alt': 15.0}, {'lng': -79.9504203, 'lat': 40.4158615, 'alt': 15.0}]"
            t = DetectTask(self.drone, self.cloudlet, **kwargs)
            self.taskQueue.put(t)
            print("Added task DetectTask to the queue")
            
            self.drone.takeOff()
            self._execLoop()
        except Exception as e:
            print(e)
