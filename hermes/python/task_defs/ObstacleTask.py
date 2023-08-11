from interfaces.Task import Task
import json

class ObstacleTask(Task):

    def __init__(self, drone, cloudlet, **kwargs):
        super(drone, cloudlet, kwargs)
        self.altitude = None
        self.speed = None
        self.model = None
        self.coords = None
        try:
            if "altitude" in kwargs:
                self.altitude = kwargs["altitude"]
            if "speed" in kwargs:
                self.speed = kwargs["speed"]
            if "model" in kwargs:
                self.model = kwargs["model"]
            if "coords" in kwargs:
                self.coords = [kwargs["coords"][0], kwargs["coords"][1]]
        except Exception as e:
            print(e)

    def run(self):
        print("-------SCRIPT STARTED--------")
