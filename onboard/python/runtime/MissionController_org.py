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
        if (triggered_event == "timeout"):
            return "task2"
        if (triggered_event == "detected"):
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
        # define start task
        print("MissionController: define the tasks\n")
        self.start_task_id = "task1"
        
        
        #define transition
        print("MissionController: define the transitions\n")
        transition_args_1 = {}
        transition_args_1["timer"] = 120
        transition_args_1["object_detection"] = "person"
        
        transition_args_2 = {}
        self.transitMap["task1"]= self.task1_transit
        self.transitMap["task2"]= self.task2_transit
        self.transitMap["default"]= self.default_transit
        
        kwargs = {}
        # TASKtask1
        kwargs.clear()
        #task
        kwargs["gimbal_pitch"] = "-45.0"
        kwargs["drone_rotation"] = "0.0"
        kwargs["sample_rate"] = "2"
        kwargs["hover_delay"] = "0"
        kwargs["model"] = "coco"
        kwargs["coords"] = "[{'lng': -79.949905, 'lat': 40.4153, 'alt': 15.0}, {'lng': -79.95023, 'lat': 40.4153, 'alt': 15.0}, {'lng': -79.95005, 'lat': 40.41511, 'alt': 15.0}, {'lng': -79.949905, 'lat': 40.4153, 'alt': 15.0}]"
        task1 = DetectTask(self.drone, self.cloudlet, "task1", self.trigger_event_queue, transition_args_1, **kwargs)
        self.taskMap["task1"] = task1
        
        # TASKtask2
        kwargs.clear()
        kwargs["gimbal_pitch"] = "-45.0"
        kwargs["drone_rotation"] = "0.0"
        kwargs["sample_rate"] = "2"
        kwargs["hover_delay"] = "0"
        kwargs["model"] = "coco"
        kwargs["coords"] = "[{'lng': -79.95027, 'lat': 40.415672, 'alt': 25.0}, {'lng': -79.950264, 'lat': 40.41546, 'alt': 25.0}, {'lng': -79.94991, 'lat': 40.415455, 'alt': 25.0}, {'lng': -79.94991, 'lat': 40.415676, 'alt': 25.0}, {'lng': -79.95027, 'lat': 40.415672, 'alt': 25.0}]"
        task2 = DetectTask(self.drone, self.cloudlet, "task2", self.trigger_event_queue, transition_args_2, **kwargs)
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
        

