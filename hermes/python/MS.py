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
            # DetectTask/DetectTask START
            kwargs.clear()
            kwargs["gimbal_pitch"] = "-45.0"
            kwargs["drone_rotation"] = "0.0"
            kwargs["sample_rate"] = "2"
            kwargs["hover_delay"] = "5"
            kwargs["model"] = "coco"
            kwargs["coords"] = "[{'lng': 2.3674155, 'lat': 48.8790452, 'alt': 15.0}, {'lng': 2.3669702, 'lat': 48.8791051, 'alt': 15.0}, {'lng': 2.3667288, 'lat': 48.8787806, 'alt': 15.0}, {'lng': 2.3672223, 'lat': 48.8785265, 'alt': 15.0}, {'lng': 2.3677963, 'lat': 48.8786359, 'alt': 15.0}, {'lng': 2.3674155, 'lat': 48.8790452, 'alt': 15.0}]"
            t = DetectTask(self.drone, self.cloudlet, **kwargs)
            self.taskQueue.put(t)
            print("Added task DetectTask to the queue")
            
            self.drone.takeOff()
            self._execLoop()
        except Exception as e:
            print(e)
