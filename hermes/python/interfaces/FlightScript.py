import queue

class FlightScript:

    def __init__(self, drone, cloudlet):
        self.drone = drone
        self.cloudlet = cloudlet
        self.taskThread = None
        self.taskQueue = queue.Queue()

    def _execLoop(self):
        try:
            while not self.taskQueue.empty():
                self._exec(self.taskQueue.get())
        except Exception as e:
            print(f'Exec loop interrupted by exception: {e}') 

    def _exec(self, task):
        self.currentTask = task
        self.taskThread = task
        self.taskThread.start()
        self.taskThread.join()

    def _kill(self):
        try:
            self.taskThread.stop()
        except RuntimeError as e:
            print(e)
        thread_id = self.get_id()
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            raise RuntimeError('Error killing flight script thread')

    def _pause(self):
        pass

    def _push_task(self, task):
        self.taskQueue.put(task)

    def _force_task(self, task):
        pass
