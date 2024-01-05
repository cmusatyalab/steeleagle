import threading
from interfaces.Task import Task
import time
import ast

class DetectTask(Task):

    def __init__(self, drone, task_id, event_queue,**kwargs):
        super().__init__(drone, task_id, **kwargs)
        self.event_queue = event_queue

    def trigger_event(self, event):
        print(f"**************Detect Task {self.task_id}: triggered event! {event}**************\n")
        self.event_queue.put((self.task_id,  event))

    def run(self):
        # triggered event
        if (self.task_id == "task1"):
            # construct the timer with 90 seconds
            timer = threading.Timer(90, self.trigger_event, ["timeout"])
            timer.daemon = True
            # Start the timer
            timer.start()
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
            self.trigger_event("done")
        except Exception as e:
            print(e)


