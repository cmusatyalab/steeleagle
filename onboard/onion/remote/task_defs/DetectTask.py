
from transition_defs.TransObjectDetection import TransObjectDetection
from transition_defs.TransTimer import TransTimer
from interfaces.Task import Task
import time
import ast
import logging
from gabriel_protocol import gabriel_pb2


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class DetectTask(Task):

    def __init__(self, drone, cloudlet, task_id, trigger_event_queue,**kwargs):
        super().__init__(drone, cloudlet, task_id, trigger_event_queue, **kwargs)
        
    def run(self):
        # init the cloudlet
        self.cloudlet.switchModel(self.kwargs["model"])
        args = {
            'task_id': self.task_id,
            'trans_active': self.trans_active,
            'trans_active_lock': self.trans_active_lock,
            'trigger_event_queue': self.trigger_event_queue
        }
        
        # triggered event
        if (self.task_id == "task1"):
            timer = TransTimer(args, 120)
            timer.daemon = True
            timer.start()
            
        if (self.task_id == "task1"):
            object_trans = TransObjectDetection(args, "person", self.cloudlet)
            object_trans.daemon = True
            object_trans.start()
            
            
        try:
            print(f"**************Detect Task {self.task_id}: hi this is detect task {self.task_id}**************\n")
            coords = ast.literal_eval(self.kwargs["coords"])
            self.drone.setGimbalPose(0.0, float(self.kwargs["gimbal_pitch"]), 0.0)
            hover_delay = int(self.kwargs["hover_delay"])
            for dest in coords:
                lng = dest["lng"]
                lat = dest["lat"]
                alt = dest["alt"]
                print(f"**************Detect Task {self.task_id}: move to {lat}, {lng}, {alt}**************")
                self.drone.moveTo(lat, lng, alt)
                time.sleep(hover_delay)

            print(f"**************Detect Task {self.task_id}: Done**************\n")
            self._exit()
        except Exception as e:
            print(e)


