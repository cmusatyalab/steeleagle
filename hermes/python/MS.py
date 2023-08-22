from interfaces.FlightScript import FlightScript
# Import derived tasks
from task_defs.DetectTask import DetectTask

class MS(FlightScript):
   
    def __init__(self, drone, cloudlet):
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
            kwargs["coords"] = "[{'lng': -80.0076661, 'lat': 40.4534506, 'alt': 15.0}, {'lng': -80.0075856, 'lat': 40.4526669, 'alt': 15.0}, {'lng': -80.0061211, 'lat': 40.4526995, 'alt': 15.0}, {'lng': -80.0057885, 'lat': 40.4536384, 'alt': 15.0}, {'lng': -80.0076661, 'lat': 40.4534506, 'alt': 15.0}]"
            t = DetectTask(self.drone, self.cloudlet, **kwargs)
            self.taskQueue.put(t)
            print("Added task DetectTask to the queue")
            
            self.drone.takeOff()
            self._execLoop()
        except Exception as e:
            print(e)