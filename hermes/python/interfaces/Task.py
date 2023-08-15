import threading

class Task:

    def __init__(self, drone, cloudlet):
        self.drone = drone
        self.cloudlet = cloudlet
        self.exit = False

    # Run is already an abstract method derived from Runnable.
    # It will be implemented separately by each task.
    
    def pause(self):
        pass

    def stop(self):
        self.exit = True

    def resume(self):
        pass
