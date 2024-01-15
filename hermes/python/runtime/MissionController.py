from runtime.MissionRunner import MissionRunner
import threading
import queue


class MissionController(threading.Thread):


    def __init__(self, drone, cloudlet):
        super().__init__()
        self.trigger_event_queue = queue.Queue()
        self.mr = MissionRunner(drone, cloudlet, self.trigger_event_queue)
        self.transitMap = {
            "task1": self.task1_transit,
            "task2": self.task2_transit,
            "default": self.default_transit
        }

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
    def next_task(self, triggered_event):
        current_task_id = self.mr.get_current_task()
        next_task_id  = self.transitMap.get(current_task_id, self.default_transit)(triggered_event)
        return next_task_id
    
    def run(self):
        # start the mc
        print("MissionController: hi start the controller\n")
        
        # init the mission runner
        self.mr.start()
        print("MissionController: init the mission runner\n")
        
        # main logic check the triggered event
        while True:
            item = self.trigger_event_queue.get()
            if item is not None:
                print(f"MissionController: Trigger one event {item} \n")
                print(f"MissionController: Task id  {item[0]} \n")
                print(f"MissionController: event   {item[1]} \n")
                if (item[0] == self.mr.get_current_task()):
                    next_task_id = self.next_task(item[1])
                    if (next_task_id == "terminate"):
                        break
                    else:
                        self.mr.transit_to(next_task_id)
                        
        # terminate the mr          
        print(f"MissionController: the current task is done, terminate the MISSION RUNNER \n")
        self.mr.end_mission()
        
        #end the mc              
        print("MissionController: terminate the controller\n")           
        

