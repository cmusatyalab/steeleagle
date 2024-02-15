import threading
from interfaces.Transition import Transition

class TransTimer (Transition):
    def __init__(self, args, timer_interval):
        super().__init__(args)
        # Create a Timer within the thread
        self.timer = threading.Timer(timer_interval, self._trigger_event, ["timeout"])
        self.completed = True
        
    def stop (self):
        self.timer.cancel()
        self.completed = False
        
    def run(self):
        self._register()
        self.timer.start()
        self.timer.join()  # Optionally wait for the timer to finish
        if (self.completed):
            print(f"**************Transition: Task {self.task_id}: timeout!**************\n")
        self._unregister()