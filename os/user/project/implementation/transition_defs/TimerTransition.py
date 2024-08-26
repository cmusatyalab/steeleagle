import logging
import threading
from project.interface.Transition import Transition

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class TimerTransition (Transition):
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
            logger.info(f"**************Transition: Task {self.task_id}: timeout!**************\n")
        self._unregister()