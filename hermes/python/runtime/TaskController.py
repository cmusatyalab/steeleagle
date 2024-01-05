import threading


class TaskController(threading.Thread):


    def __init__(self, mr):
        super().__init__()
        self.mr = mr
        self.event_queue = mr.event_queue
        self.transitMap = {
            "task1": self.task1_transit,
            "task2": self.task2_transit,
            "default": self.default_transit
        }

    @staticmethod
    def task1_transit(triggered_event):
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
        print(f"no matched up transition, triggered event {triggered_event}\n", triggered_event)
    def next_task(self, triggered_event):
        current_task_id = self.mr.get_current_task()
        next_task_id  = self.transitMap.get(current_task_id, self.default_transit)(triggered_event)
        self.mr.transit_to(next_task_id)
        return next_task_id
    def run(self):
        print("hi start the controller\n")
        # check the triggered event
        while True:
            item = self.event_queue.get()
            if item is not None:
                print(f"Controller: Trigger one event {item} \n")
                print(f"Controller: Task id  {item[0]} \n")
                print(f"Controller: event   {item[1]} \n")
                if (item[0] == self.mr.get_current_task()):
                    next_task_id = self.next_task(item[1])
                    if (next_task_id == "terminate"):
                        print(f"Controller: the current task is done, terminate the controller \n")
                        break

