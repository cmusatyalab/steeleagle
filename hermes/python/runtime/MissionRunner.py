from interfaces.FlightScript import FlightScript

class MissionRunner(FlightScript):
    
    # private method
    def __init__(self, drone, start_task_id):
        super().__init__(drone)
        self.curr_task_id = None
        self.start_task_id = start_task_id
        
    def start_mission(self, task):
       # set the current task
       self.curr_task_id = task.task_id
       print(f"MR: start mission, current taskid:{self.curr_task_id}\n")
       # start
       self._push_task(task)
       print("MR: taking off")
       self.drone.takeOff()
       self._execLoop()
    
    #public method    
    def transit_to(self, task):
        print(f"MR: transit to task with task_id: {task.task_id}, current_task_id: {self.curr_task_id}")
        self._kill()
        self._push_task(task)
        self.curr_task_id = task.task_id
       
    def end_mission(self):
        self._stopLoop()
        print("MR: end mission, rth\n")
        self.drone.moveTo(40.4156235, -79.9504726 , 20)
        print("MR: land")
        self.drone.land()
        
    def get_current_task(self):
        return self.curr_task_id
    
    def run(self):
        try:
            # start mission
            print("MR: start the mission!\n")
            self.start_mission()
        except Exception as e:
            print(e)
