import threading
import queue

class FlightScript(threading.Thread):

    def __init__(self, drone, cloudlet):
        self.drone = drone
        self.cloudlet = cloudlet
        self.taskThread = None
        self.taskQueue = queue.Queue()

    def run(self): # To be implemented
        pass

    def _execLoop(self):
        while not self.taskQueue.empty():
            self._exec(self.taskQueue.get())

    def _exec(self, task):
        self.currentTask = task
        self.taskThread = task
        self.taskThread.start()

    def _kill(self):
        self.taskQueue.clear()
        self.taskThread.stop()
        self.drone.kill()

    def _pause(self):
        pass

    def _push_task(self, task):
        self.taskQueue.put(task)

    def _force_task(self, task):
        pass
