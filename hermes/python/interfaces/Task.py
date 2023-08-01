import threading

class Task(threading.Thread):

    def __init__(self, drone, cloudlet, **kwargs):
        self.drone = drone
        self.cloudlet = cloudlet
        self.kwargs = kwargs
        self.exit = False

    # Run is already an abstract method derived from Runnable.
    # It will be implemented separately by each task.
    
    def pause(self):
        pass

    def stop(self):
        self.exit = True

    def resume(self):
        pass
