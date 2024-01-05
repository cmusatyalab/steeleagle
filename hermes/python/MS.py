import threading
from runtime.MissionRunner import MissionRunner
from runtime.TaskController import TaskController
from interfaces.FlightScript import FlightScript


class MS(threading.Thread):
   
    def __init__(self, drone):
        threading.Thread.__init__(self)
        self.drone = drone
 
    def run(self):
        # init the mission runner
        mr = MissionRunner(self.drone)
        print("init the mission runner\n")

        # context switch controller
        tc =  TaskController(mr)
        print("init the task switch controller\n")


        # running the program
        print("run the flight mission\n")
        tc.start()
        mr.start()

        tc.join()
        mr.join()