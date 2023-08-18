import threading

class Task:

    def __init__(self, drone, cloudlet, **kwargs):
        self.drone = drone
        self.cloudlet = cloudlet
        self.kwargs = kwargs

    # Run is already an abstract method derived from Runnable.
    # It will be implemented separately by each task.
    
    def pause(self):
        pass

    def stop(self):
        raise RuntimeError("Task killed by mission script, terminating...")

    def resume(self):
        pass
