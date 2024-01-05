import threading
import ctypes

class Task(threading.Thread):

    def __init__(self, drone, task_id,**kwargs):
        threading.Thread.__init__(self)
        self.drone = drone
        self.kwargs = kwargs
        self.task_id = task_id

    # Run is already an abstract method derived from Runnable.
    # It will be implemented separately by each task.
    
    def pause(self):
        pass
    
    def get_task_id(self):
        return self.task_id

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

    def stop(self):
        thread_id = self._get_id()
        if thread_id != None:
            res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread_id), ctypes.py_object(SystemExit))
            if res > 1:
                ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
                raise RuntimeError('Error killing task thread')

    def resume(self):
        pass
