from interfaces.Task import Task
import json
import time

class ObstacleTask(Task):

    def __init__(self, drone, cloudlet, **kwargs):
        super(drone, cloudlet, kwargs)

    def run(self):
        print("-------SCRIPT STARTED--------")
        self.drone.takeOff()
