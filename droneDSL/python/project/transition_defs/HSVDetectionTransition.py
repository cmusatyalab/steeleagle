from json import JSONDecodeError
import json
import logging
from venv import logger
from interface.Transition import Transition
from gabriel_protocol import gabriel_pb2

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class HSVDetectionTransition(Transition):
    def __init__(self, args, target,  cloudlet):
        super().__init__(args)
        self.stop_signal = False
        self.target = target
        self.cloudlet = cloudlet
        
    def stop(self):
        self.stop_signal = True
    
    def run(self):
        self._register()
        self.cloudlet.clearResults("openscout-object")
        while not self.stop_signal:
            result = self.cloudlet.getResults("openscout-object")
            if (result != None):
                if result.payload_type == gabriel_pb2.TEXT:
                    try:
                        json_string = result.payload.decode('utf-8')
                        json_data = json.loads(json_string)
                        for item in json_data:
                            class_attribute = item['class']
                            hsv_filter = item['hsv_filter']
                            if (class_attribute == self.target and hsv_filter):
                                    logger.info(f"**************Transition: Task {self.task_id}: detect condition met! {class_attribute}**************\n")
                                    self._trigger_event("hsv_detection")
                                    break
                    except JSONDecodeError as e:
                        logger.error(f'Error decoding json: {json_string}')
                    except Exception as e:
                        logger.info(e)
      
        self._unregister()
  
    
