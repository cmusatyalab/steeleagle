from json import JSONDecodeError
import json
from venv import logger
from interfaces.Transition import Transition
from gabriel_protocol import gabriel_pb2


class TransObjectDetection(Transition):
    def __init__(self, args, target, cloudlet):
        super().__init__(args)
        self.stop_signal = False
        self.target =target
        self.cloudlet = cloudlet
        
    def stop(self):
        self.stop_signal = True
    
    def run(self):
        self._register()
        while not self.stop_signal:
            # Replace this with your actual condition
            result = self.cloudlet.getResults("openscout-object")
            if (result != None):
                print(f"**************Transition:  Task {self.task_id}: detected payload! {result}**************\n")
                # Check if the payload type is TEXT, since your JSON seems to be text data
                if result.payload_type == gabriel_pb2.TEXT:
                    try:
                        # Decode the payload from bytes to string
                        json_string = result.payload.decode('utf-8')

                        # Parse the JSON string
                        json_data = json.loads(json_string)

                        # Access the 'class' attribute
                        class_attribute = json_data[0]['class']  # Adjust the indexing based on your JSON structure
                        print(class_attribute)

                        if (class_attribute== self.target):
                                print(f"**************Transition: Task {self.task_id}: detect condition met! {class_attribute}**************\n")
                                self._trigger_event("object_detection")
                                break
                    except JSONDecodeError as e:
                        logger.error(f'Error decoding json: {json_string}')
                    except Exception as e:
                        print(e)
        # print("object stopping...\n")          
        self._unregister()
  
    