from interfaces.Task import Task
import threading
import json
import time

class ObstacleTask(Task, threading.Thread):

    def __init__(self, drone, cloudlet, **kwargs):
        threading.Thread.__init__(self)
        super().__init__(drone, cloudlet, **kwargs)

    def run(self):
        # TODO: To be implemented
        pass
