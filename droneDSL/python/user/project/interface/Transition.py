from abc import ABC, abstractmethod
import logging
import threading


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class Transition(threading.Thread, ABC):
    def __init__(self, args):
        super().__init__()
        self.task_id = args['task_id']
        self.trans_active = args['trans_active']
        self.trans_active_lock = args['trans_active_lock']
        self.trigger_event_queue = args['trigger_event_queue']
        # self.trigger_event_queue_lock = trigger_event_queue_lock
        
    @abstractmethod
    def stop(self):
        """This is an abstract method that must be implemented in a subclass."""
        pass
    
    def _trigger_event(self, event):
        logger.info(f"**************task id {self.task_id}: triggered event! {event}**************\n")
        # with self.trigger_event_queue_lock:
        self.trigger_event_queue.put((self.task_id,  event))
    
    def _register(self):
        logger.info(f"**************{self.name} is registering by itself**************\n")
        with self.trans_active_lock:
            self.trans_active.append(self)
            
    def _unregister(self):
        logger.info(f"**************{self.name} is unregistering by itself**************\n")
        with self.trans_active_lock:
            self.trans_active.remove(self)
        