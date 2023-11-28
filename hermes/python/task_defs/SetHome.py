from interfaces.Task import Task
import time
import ast

class DetectTask(Task):

    def __init__(self, drone, cloudlet, **kwargs):
        super().__init__(drone, cloudlet, **kwargs)

    def run(self):
        try:
            coords = ast.literal_eval(self.kwargs["coords"])
            lat = coords[0]["lat"]
            lng = coords[0]["lng"]
            self.drone.setHome(lat, lng)
        except Exception as e:
            print(e)


