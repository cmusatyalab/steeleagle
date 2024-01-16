
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

    def __init__(self, drone, cloudlet, task_id, trigger_event_queue, transition_args, **kwargs):
        super().__init__(drone, cloudlet, task_id, trigger_event_queue, **kwargs)
        self.transition_args = transition_args
        
    def create_transition(self):
        
        print(f"**************Detect Task {self.task_id}: create transition! **************\n")
        print(self.transition_args)
        args = {
            'task_id': self.task_id,
            'trans_active': self.trans_active,
            'trans_active_lock': self.trans_active_lock,
            'trigger_event_queue': self.trigger_event_queue
        }
        
        # triggered event
        if ("timer" in self.transition_args):
            print(f"**************Detect Task {self.task_id}: trigger timer! **************\n")
            timer = TransTimer(args, self.transition_args["timer"])
            timer.daemon = True
            timer.start()
            
        if ("object_detection" in self.transition_args):
            print(f"**************Detect Task {self.task_id}: trigger object detection! **************\n")
            object_trans = TransObjectDetection(args, self.transition_args["object_detection"], self.cloudlet)
            object_trans.daemon = True
            object_trans.start()
            
    def run(self):
        # init the cloudlet
        self.cloudlet.switchModel(self.kwargs["model"])
        
        self.create_transition()
        
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


