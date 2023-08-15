from interfaces.Task import Task
import threading
import json
import time

class ObstacleTask(Task, threading.Thread):

    def __init__(self, drone, cloudlet, **kwargs):
        threading.Thread.__init__(self)
        super().__init__(drone, cloudlet, **kwargs)

    def run(self):
        print("TASK STARTED ---------------")
        self.drone.moveBy(0.0, 5.0, 0.0, 0.0)
        time.sleep(5)
        print("TASK FINISHED --------------")
