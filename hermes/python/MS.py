from interfaces.FlightScript import FlightScript
# Import derived tasks
from task_defs.ObstacleTask import ObstacleTask
from task_defs.ObstacleTask import ObstacleTask

class MS(FlightScript):
    
    def run(self):
        try:
            # Avoid1/ObstacleTask START
            kwargs.clear()
            kwargs["model"] = "DPT_Large"
            kwargs["speed"] = "10"
            kwargs["altitude"] = "52.0"
            kwargs["coords"] = "[{'lng': -79.9611343, 'lat': 40.428706, 'alt': 15.0}, {'lng': -79.9603994, 'lat': 40.428022, 'alt': 15.0}]"
            t = ObstacleTask(self.drone, self.cloudlet, **kwargs)
            self.taskQueue.put(t)
            # Avoid2/ObstacleTask START
            kwargs.clear()
            kwargs["model"] = "DPT_Large"
            kwargs["speed"] = "10"
            kwargs["altitude"] = "52.0"
            kwargs["coords"] = "[{'lng': -79.95993, 'lat': 40.4282537, 'alt': 15.0}, {'lng': -79.9607105, 'lat': 40.4289296, 'alt': 15.0}]"
            t = ObstacleTask(self.drone, self.cloudlet, **kwargs)
            self.taskQueue.put(t)
            
            self.drone.takeOff()
            self._execLoop()
        except Exception as e:
            pass
