from interfaces.FlightScript import FlightScript
# Import derived tasks
from task_defs.DetectTask import DetectTask
import queue


class MissionRunner(FlightScript):
    def __init__(self, drone, cloudlet):
        super().__init__(drone, cloudlet)
        self.curr_task_id = None
        self.taskMap = {}
        self.event_queue = queue.Queue()
        self.task1 = None
        self.task2 = None
    def define_task(self, event_queue):
        # Define task
        kwargs = {}
        # TASKtask1
        kwargs.clear()
        kwargs["gimbal_pitch"] = "-45.0"
        kwargs["drone_rotation"] = "0.0"
        kwargs["sample_rate"] = "2"
        kwargs["hover_delay"] = "0"
        kwargs["model"] = "coco"
        kwargs["coords"] = "[{'lng': -79.95027, 'lat': 40.415672, 'alt': 25.0}, {'lng': -79.950264, 'lat': 40.41546, 'alt': 25.0}, {'lng': -79.94991, 'lat': 40.415455, 'alt': 25.0}, {'lng': -79.94991, 'lat': 40.415676, 'alt': 25.0}, {'lng': -79.95027, 'lat': 40.415672, 'alt': 25.0}]"
        self.task1 = DetectTask(self.drone, self.cloudlet, "task1", event_queue, **kwargs)
        self.taskMap["task1"] = self.task1
        # TASKtask2
        kwargs.clear()
        kwargs["gimbal_pitch"] = "-45.0"
        kwargs["drone_rotation"] = "0.0"
        kwargs["sample_rate"] = "2"
        kwargs["hover_delay"] = "0"
        kwargs["model"] = "coco"
        kwargs["coords"] = "[{'lng': -79.949905, 'lat': 40.4153, 'alt': 25.0}, {'lng': -79.95023, 'lat': 40.4153, 'alt': 25.0}, {'lng': -79.95005, 'lat': 40.41511, 'alt': 25.0}, {'lng': -79.949905, 'lat': 40.4153, 'alt': 25.0}]"
        self.task2 = DetectTask(self.drone, self.cloudlet, "task2", event_queue, **kwargs)
        self.taskMap["task2"] = self.task2
    def transit_to(self, task_id):
        print(f"MR: transit to task with task_id: {task_id}, current_task_id: {self.curr_task_id}")
        self.set_current_task(task_id)
        self._kill()
        if (task_id != "terminate"):
            self._push_task(self.taskMap[task_id])
            self._execLoop()
        else:
            self.end_mission()
    def start_mission(self):
       # set the current task
       task_id = self.task2.get_task_id()
       self.set_current_task(task_id)
       print(f"MR: start mission, current taskid:{task_id}\n")
       # start
       self.taskQueue.put(self.task2)
       print("MR: taking off")
       self.drone.takeOff()
       self._execLoop()
    def end_mission(self):
        print("MR: end mission, rth\n")
        self.drone.moveTo(40.4156235, -79.9504726 , 20)
        print("MR: land")
        self.drone.land()
    def set_current_task(self, task_id):
        self.curr_task_id = task_id
    def get_current_task(self):
        return self.curr_task_id
    def run(self):
        try:
            # define task
            print("MR: define the tasks\n")
            self.define_task(self.event_queue)
            # start mission
            print("MR: start the mission!\n")
            self.start_mission()
        except Exception as e:
            print(e)
