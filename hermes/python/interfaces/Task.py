# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import asyncio
import ctypes
from abc import ABC, abstractmethod

class Task(ABC):

    def __init__(self, drone, cloudlet, task_id, trigger_event_queue, task_args):
        threading.Thread.__init__(self)
    def __init__(self, drone, cloudlet, **kwargs):
        self.drone = drone
        self.cloudlet = cloudlet
        self.kwargs = kwargs

    @abstractmethod
    async def run(self):
        pass

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

    def _exit(self):
        # kill all the transitions
        for trans in self.trans_active:
            if trans.is_alive():
                trans.stop()
                trans.join()
        self.trigger_event_queue.put((self.task_id,  "done")) 
        
    def stop(self):
        # kill all the transitions
        # print(self.trans_active)
        for trans in self.trans_active:
            if trans.is_alive():
                trans.stop()
                trans.join()
            
                    
        # kill the task itself
        thread_id = self._get_id()
        if thread_id != None:
            res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread_id), ctypes.py_object(SystemExit))
            if res > 1:
                ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
                raise RuntimeError('Error killing task thread')

    def resume(self):
        pass
