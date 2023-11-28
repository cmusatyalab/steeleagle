from interfaces.FlightScript import FlightScript
# Import derived tasks
from task_defs.DetectTask import DetectTask

class MS(FlightScript):
   
    def __init__(self, drone, cloudlet):
        super().__init__(drone, cloudlet)
 
    def run(self):
        try:
            kwargs = {}
            # Pacman/DetectTask START
            kwargs.clear()
            kwargs["gimbal_pitch"] = "-45.0"
            kwargs["drone_rotation"] = "0.0"
            kwargs["sample_rate"] = "2"
            kwargs["hover_delay"] = "0"
            kwargs["model"] = "coco"
            kwargs["coords"] = "[{'lng': -79.9503727, 'lat': 40.4154746, 'alt': 25.0}, {'lng': -79.9497505, 'lat': 40.4152295, 'alt': 25.0}, {'lng': -79.9501689, 'lat': 40.4149395, 'alt': 25.0}, {'lng': -79.9498631, 'lat': 40.4147843, 'alt': 25.0}, {'lng': -79.9492838, 'lat': 40.4148537, 'alt': 25.0}, {'lng': -79.9491443, 'lat': 40.4153112, 'alt': 25.0}, {'lng': -79.9492945, 'lat': 40.4157074, 'alt': 25.0}, {'lng': -79.9499704, 'lat': 40.415789, 'alt': 25.0}, {'lng': -79.9503727, 'lat': 40.4154746, 'alt': 25.0}]"
            t = DetectTask(self.drone, self.cloudlet, **kwargs)
            self.taskQueue.put(t)
            print("Added task DetectTask to the queue")
            
            self.drone.takeOff()
            self._execLoop()
        except Exception as e:
            print(e)