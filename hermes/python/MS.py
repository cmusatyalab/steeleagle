import threading
from runtime.MissionController import MissionController


class MS(threading.Thread):
   
    def __init__(self, drone, cloudlet):
        threading.Thread.__init__(self)
        

        # context switch controller
        self.mc =  MissionController(drone, cloudlet)
        print("MS: init the Mission controller\n")

 
    def run(self):
        # running the program
        print("MS: run the flight mission\n")
        self.mc.start()
    

        self.mc.join()
 