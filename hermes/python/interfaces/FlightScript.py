import queue
import threading

class FlightScript(threading.Thread):

    def __init__(self, drone, cloudlet):
        threading.Thread.__init__(self)
        self.cloudlet = cloudlet
        self.drone = drone
        self.taskThread = None
        self.taskQueue = queue.Queue()
        self._stop_loop_event = threading.Event()
        
        
    def _push_task(self, task):
        self.taskQueue.put(task)

    def _stopLoop(self):
        self._stop_loop_event.set()
    
    def _execLoop(self):
        try:
            while not self._stop_loop_event.is_set():
                if (not self.taskQueue.empty()):
                    self.taskThread = self.taskQueue.get()
                    self._exec(self.taskThread)
        except Exception as e:
            print(f'Exec loop interrupted by exception: {e}')

    def _exec(self, task):
        self.taskThread = task
        self.taskThread.start()
        
    def _kill(self):
        try:
            if self.taskThread is not None:
                self.taskThread.stop()
            else:
                print(f"FlightScript: no task thread is running")
        except RuntimeError as e:
            print(f"FlightScript: ", e)
            
    def _get_id(self):
        if not self.is_alive():
            raise threading.ThreadError("the thread is not active")

        # do we have it cached?
        if hasattr(self, "_thread_id"):
            return self._thread_id

        # no, look for it in the _active dict
        for tid, tobj in threading._active.items():
            if tobj is self:
                self._thread_id = tid
                return tid


    def _pause(self):
        pass

    def _force_task(self, task):
        pass
