import threading
from interfaces.Task import Task
import time
import ast
from json import JSONDecodeError
import json
import logging
from gabriel_protocol import gabriel_pb2

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class DetectTask(Task):

    def __init__(self, drone, cloudlet, task_id, trigger_event_queue,**kwargs):
        super().__init__(drone, cloudlet, task_id, **kwargs)
        self.trigger_event_queue = trigger_event_queue

    def trigger_event(self, event):
        print(f"**************Detect Task {self.task_id}: triggered event! {event}**************\n")
        self.trigger_event_queue.put((self.task_id,  event))
    
    def check_condition(self):
        while True:
            # Replace this with your actual condition
            result = self.cloudlet.getResults("openscout-object")
            if (result != None):
                print(f"**************Detect Task {self.task_id}: detected payload! {result}**************\n")
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

                        if (class_attribute=="person"):
                                print(f"**************Detect Task {self.task_id}: detect condition met! {class_attribute}**************\n")
                                self.trigger_event("detected")
                                return
                    except JSONDecodeError as e:
                        logger.error(f'Error decoding json: {json_string}')
                    except Exception as e:
                        print(e)


    def run(self):
        # init the cloudlet
        self.cloudlet.switchModel(self.kwargs["model"])
        
        # triggered event
        if (self.task_id == "task1"):
            # construct the timer with 90 seconds
            timer = threading.Timer(120, self.trigger_event, ["timeout"])
            timer.daemon = True
            # Start the timer
            timer.start()
            
        if (self.task_id == "task1"):
            # Creating the thread
            object_trans = threading.Thread(target=self.check_condition)
            # Starting the thread
            object_trans.start()
            
            
        try:
            print(f"**************Detect Task {self.task_id}: hi this is detect task {self.task_id}**************\n")
            coords = ast.literal_eval(self.kwargs["coords"])
            self.drone.setGimbalPose(0.0, float(self.kwargs["gimbal_pitch"]), 0.0)
            hover_delay = int(self.kwargs["hover_delay"])
            for dest in coords:
                lng = dest["lng"]
                lat = dest["lat"]
                alt = dest["alt"]
                print(f"**************Detect Task {self.task_id}: move to {lat}, {lng}, {alt}**************")
                self.drone.moveTo(lat, lng, alt)
                time.sleep(hover_delay)

            print(f"**************Detect Task {self.task_id}: Done**************\n")
            self.trigger_event("done")
        except Exception as e:
            print(e)


