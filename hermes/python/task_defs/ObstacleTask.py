from interfaces.Task import Task
import json
import time

class ObstacleTask(Task):

    def __init__(self, drone, cloudlet, **kwargs):
        super().__init__(drone, cloudlet, **kwargs)

    def run(self):
        # TODO: To be implemented
        pass
