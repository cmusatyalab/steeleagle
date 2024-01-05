import threading
from runtime.MissionRunner import MissionRunner
from runtime.TaskController import TaskController


class MS(threading.Thread):
   
    def __init__(self, drone, cloudlet):
        threading.Thread.__init__(self)
        
        # init the mission runner
        self.mr = MissionRunner(drone, cloudlet)
        print("MS: init the mission runner\n")

        # context switch controller
        self.tc =  TaskController(self.mr)
        print("MS: init the task switch controller\n")

 
    def run(self):
        # running the program
        print("MS: run the flight mission\n")
        self.tc.start()
        self.mr.start()

        self.tc.join()
        self.mr.join()