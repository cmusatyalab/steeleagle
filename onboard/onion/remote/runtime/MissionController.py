from task_defs.DetectTask import DetectTask
from runtime.MissionRunner import MissionRunner
import threading
import queue


class MissionController(threading.Thread):


    def __init__(self, drone, cloudlet):
        super().__init__()
        self.trigger_event_queue = queue.Queue()
        self.drone = drone
        self.cloudlet = cloudlet
        self.start_task_id = None
        self.taskMap = {}
        self.transitMap = {}

    # transition
    @staticmethod
    def task1_transit(triggered_event):
        if (triggered_event == "object_detection"):
            return "task2"

        if (triggered_event == "done"):
            return "terminate"

    @staticmethod
    def task2_transit(triggered_event):
        if (triggered_event == "timeout"):
            return "task1"

        if (triggered_event == "done"):
            return "terminate"

    @staticmethod
    def default_transit(triggered_event):
        print(f"MissionController: no matched up transition, triggered event {triggered_event}\n", triggered_event)
    #task
    def define_mission(self):
        # define start task
        print("MissionController: define the tasks\n")
        self.start_task_id = "task1"

        #define transition
        print("MissionController: define the transitions\n")

        transition_args_task1 = {}
        self.transitMap["task1"]= self.task1_transit
        transition_args_task1["object_detection"] = "person"
        transition_args_task2 = {}
        self.transitMap["task2"]= self.task2_transit
        transition_args_task2["timeout"] = 10.0
        self.transitMap["default"]= self.default_transit
        kwargs = {}
        # TASKtask1
        kwargs.clear()
        kwargs["gimbal_pitch"] = "-45.0"
        kwargs["drone_rotation"] = "0.0"
        kwargs["sample_rate"] = "2"
        kwargs["hover_delay"] = "0"
        kwargs["coords"] = "[{'lng': -79.9499065, 'lat': 40.4152976, 'alt': 15}, {'lng': -79.9502364, 'lat': 40.4152976, 'alt': 15}, {'lng': -79.950054, 'lat': 40.4151098, 'alt': 15}, {'lng': -79.9499065, 'lat': 40.4152976, 'alt': 15}]"
        kwargs["model"] = "coco"
        task1 = DetectTask(self.drone, self.cloudlet, "task1", self.trigger_event_queue, transition_args_task1, **kwargs)
        self.taskMap["task1"] = task1
        # TASKtask2
        kwargs.clear()
        kwargs["gimbal_pitch"] = "-45.0"
        kwargs["drone_rotation"] = "0.0"
        kwargs["sample_rate"] = "2"
        kwargs["hover_delay"] = "0"
        kwargs["coords"] = "[{'lng': -79.9502696, 'lat': 40.4156737, 'alt': 25}, {'lng': -79.9502655, 'lat': 40.4154588, 'alt': 25}, {'lng': -79.9499142, 'lat': 40.4154567, 'alt': 25}, {'lng': -79.9499128, 'lat': 40.4156753, 'alt': 25}, {'lng': -79.9502696, 'lat': 40.4156737, 'alt': 25}]"
        kwargs["model"] = "coco"
        task2 = DetectTask(self.drone, self.cloudlet, "task2", self.trigger_event_queue, transition_args_task2, **kwargs)
        self.taskMap["task2"] = task2

    def next_task(self, current_task_id, triggered_event):
        next_task_id  = self.transitMap.get(current_task_id, self.default_transit)(triggered_event)
        return next_task_id

    def run(self):
        # start the mc
        print("MissionController: hi start the controller\n")

        print("MissionController: define mission \n")
        self.define_mission()

        # init the mission runner
        print("MissionController: init the mission runner\n")
        mr = MissionRunner(self.drone, self.cloudlet, self.taskMap, self.start_task_id)
        mr.start()

        # main logic check the triggered event
        while True:
            item = self.trigger_event_queue.get()
            if item is not None:
                task_id = item[0]
                trigger_event = item[1]
                print(f"MissionController: Trigger one event! \n")
                print(f"MissionController: Task id  {task_id} \n")
                print(f"MissionController: event   {trigger_event} \n")
                if (task_id == mr.get_current_task()):
                    next_task_id = self.next_task(task_id, trigger_event)
                    if (next_task_id == "terminate"):
                        break
                    else:
                        mr.transit_to(next_task_id)

        # terminate the mr
        print(f"MissionController: the current task is done, terminate the MISSION RUNNER \n")
        mr.end_mission()

        #end the mc
        print("MissionController: terminate the controller\n")

