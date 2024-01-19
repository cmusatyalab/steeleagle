from task_defs.DetectTask import DetectTask
from runtime.MissionRunner import MissionRunner
import threading
import queue


class MissionController(threading.Thread):
    
    class TaskArguments():
        def __init__(self, transitions_attributes, task_attributes):
            self.task_attributes = task_attributes
            self.transitions_attributes = transitions_attributes
            
        
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
        
        if (triggered_event == "timeout"):
            return "task2"

        if (triggered_event == "done"):
            return "terminate"

    @staticmethod
    def task2_transit(triggered_event):
        if (triggered_event == "done"):
            return "terminate"

    @staticmethod
    def default_transit(triggered_event):
        print(f"MissionController: no matched up transition, triggered event {triggered_event}\n", triggered_event)
    #task
    def define_mission(self):
        #define transition
        print("MissionController: define the transitMap\n")        
        self.transitMap["task1"]= self.task1_transit
        self.transitMap["task2"]= self.task2_transit
        self.transitMap["default"]= self.default_transit
        
        # define task
        print("MissionController: define the tasks\n")
        
        self.start_task_id = "task1"
        # TASKtask1
        task_attr_task1 = {}
        task_attr_task1["gimbal_pitch"] = "-45.0"
        task_attr_task1["drone_rotation"] = "0.0"
        task_attr_task1["sample_rate"] = "2"
        task_attr_task1["hover_delay"] = "0"
        task_attr_task1["coords"] = "[{'lng': -79.9499065, 'lat': 40.4152976, 'alt': 15}, {'lng': -79.9502364, 'lat': 40.4152976, 'alt': 15}, {'lng': -79.950054, 'lat': 40.4151098, 'alt': 15}, {'lng': -79.9499065, 'lat': 40.4152976, 'alt': 15}]"
        task_attr_task1["model"] = "coco"
        # task1 = DetectTask(self.drone, self.cloudlet, "task1", self.trigger_event_queue, transition_args_task1, **kwargs)
        transition_attr_task1 = {}
        transition_attr_task1["object_detection"] = "person"
        transition_attr_task1["timeout"] = 90.0
        self.taskMap["task1"] = self.TaskArguments(transition_attr_task1, task_attr_task1)
        
        # TASKtask2
        task_attr_task2 ={}
        task_attr_task2["gimbal_pitch"] = "-45.0"
        task_attr_task2["drone_rotation"] = "0.0"
        task_attr_task2["sample_rate"] = "2"
        task_attr_task2["hover_delay"] = "0"
        task_attr_task2["coords"] = "[{'lng': -79.9503492, 'lat': 40.4155806, 'alt': 25}, {'lng': -79.9491717, 'lat': 40.4155826, 'alt': 25}]"
        # task_attr_task2["coords"] = "[{'lng': -79.9502696, 'lat': 40.4156737, 'alt': 25}, {'lng': -79.9502655, 'lat': 40.4154588, 'alt': 25}, {'lng': -79.9499142, 'lat': 40.4154567, 'alt': 25}, {'lng': -79.9499128, 'lat': 40.4156753, 'alt': 25}, {'lng': -79.9502696, 'lat': 40.4156737, 'alt': 25}]"
        task_attr_task2["model"] = "coco"
        # task2 = DetectTask(self.drone, self.cloudlet, "task2", self.trigger_event_queue, transition_args_task2, **kwargs)
        transition_attr_task2 = {}
        self.taskMap["task2"] = self.TaskArguments(transition_attr_task2, task_attr_task2)
        
        
    def add_task(self, task_id):
        self.taskMap[task_id] = DetectTask(self.drone, self.cloudlet, task_id, self.trigger_event_queue, self.taskMap[task_id])
        
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
        self.add_task(self.start_task_id)
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
                        self.add_task(next_task_id)
                        mr.transit_to(next_task_id)

        # terminate the mr
        print(f"MissionController: the current task is done, terminate the MISSION RUNNER \n")
        mr.end_mission()

        #end the mc
        print("MissionController: terminate the controller\n")

