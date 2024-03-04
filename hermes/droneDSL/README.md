# droneDSL Documentation



## Introduction

- This project develops a domain specific language for describing drone flight behavior.
- The project involves three modules:
  - pre-process: Extract the way points from KML file.
  - command line interface: Converts the written droneDSL to mission flight script.
  - post-process: Run the mission flight script using Olympe SDK

## Design

The droneDSL is a domain specific language that describes the drone flight behavior. The project is consists of three main module: pre process module, command line interface module, and post process module. The preprocess module allows user to parse the flight informations defined from the MyMap. User use parsed informations to write their own flight mission plan in droneDSL. The command line interface module converts the flight mission plan in droneDSL into the flight mission script written in python that use Olympe drone SDK. The post process module creates the Olympe environment that help user to run the flight script in real time.

## Architecture

![img](https://documents.lucid.app/documents/036d65a8-1197-41e7-9e98-4f0be76c5665/pages/0_0?a=4849&x=-228&y=8&w=3675&h=2262&store=1&accept=image%2F*&auth=LCA%20d99dbcf7d5f1cd692df5be88648f7184a5a7ce038381c45b088651654eb5fd96-ts%3D1701799469)

## Nomenclature

**Mission** - A mission is an automated drone flight which consists of one or more tasks that is designed by a mission planner.

**Task** - A task is a unit of work that should be completed during a mission which consists of a scope and actions. Initially tasks can be simple self-contained units or, in the future, can have dependencies on other tasks. Task ordering will be done by the mission plan generator.

**KML/KMZ** - Keyhole Markup Language is an XML document that is used to define the scope of a mission’s tasks. A KMZ file is a zipped version of a KML document that includes any additional styling resources needed for the KML document.

SteelEagle - An architecture that supports autonomous drone flight. It allows drone to execute  heavy computation task such as detection, tracking, and object avoidance by off loading the computing workload to the edge could.

## Workflow

### My maps

User login to the my maps to draw the takeoff, and flight routes for each task.

![img](https://documents.lucid.app/documents/036d65a8-1197-41e7-9e98-4f0be76c5665/pages/0_0?a=4859&x=-228&y=2434&w=2292&h=816&store=1&accept=image%2F*&auth=LCA%201d4ba1a2373e022626fb025a2edfd7c9c329fca7b5f9671193e77ed79b264e1b-ts%3D1701799469)

### Pre-process

Preprocess module requires user to use My maps to draw the drone's flight route. After drawing the flight route, user needs to download the flight mission as KML file.

The preprocess module takes KML file as an input and extract the waypoints for takeoff, and following tasks.

```
cmd: 
./gradlew :preprocess:run --args="{KML file path}"
```

```
Example of parsed result:

takeoff
[(-79.9504726, 40.4156235, 25.0)]
task 1
[(-79.9502696, 40.4156737, 25.0),(-79.9502655, 40.4154588, 25.0),(-79.9499142, 40.4154567, 25.0),(-79.9499128, 40.4156753, 25.0),(-79.9502696, 40.4156737, 25.0)]
task 2
[(-79.9499065, 40.4152976, 25.0),(-79.9502364, 40.4152976, 25.0),(-79.950054, 40.4151098, 25.0),(-79.9499065, 40.4152976, 25.0)]

```

With pre-processed way points information, user generates its own DSL based on the below template:

    Task {
        ^TaskType^ ^TaskID^ {
            ^TaskAttributeType^: ^AttributeValue^, 
            ...
            ^TaskAttributeType^: ^AttributeValue^,
        }
        
        ...
        
        ^TaskType^ ^TaskID^ {
            ^TaskAttributeType^: ^AttributeValue^, 
            ...
            ^TaskAttributeType^: ^AttributeValue^,
        }
    }
    
    Mission {
        Start { ^firstTask^ }
        Transition (^TriggeredEventType^(^TriggeredValue^)) ^TaskID^ -> ^TaskID^
        ...
        Transition (^TriggeredEventType^(^TriggeredValue^)) ^TaskID^ -> ^TaskID^
    }

Note:

- The **^** symbol include what type of information needs to be filled in the template.
- The **...** symbol means that there might be multiple same structured declaration repeated.

Keywords:

- **Task** defines a task definition section which includes all the defined tasks.
- **Mission** defines a mission definition section which includes the starting task, and all transitions from one task to another.
- **Start** defines the starting task
- **Transition** defines the current task (on the LHS of "->" ) under what triggered event will transit to another task (on the RHS of "->" )

Semantics:

- **TaskType**:
  - Detect (Task Type)
  - Track (Task Type)
  - Object Avoidance (Task Type)
- **TaskID**:
  - name of the task (String)

- **TaskAttributeType**:
  - way_points (Attribute Type)
  - gimbal_pitch (Attribute Type)
  - drone_rotation (Attribute Type)
  - sample_rate (Attribute Type)
  - hover_delay (Attribute Type)
  - model (Attribute Type)
- **AttributeValue**:
  - way point list (list of tuple(Double, Double, Double))
  - number (Integer, Double)
  - name (String)
- **TriggeredEventType**:
  - Timeup (Event type)
  - Detected (Event type)
- **TriggeredValue**:
  - seconds (Double)
  - colors (String)

example:

    Task {
        Detect task1 {
            way_points: [(-79.9503492, 40.4155806, 25.0),(-79.9491717, 40.4155826, 25.0)],
            gimbal_pitch: -45.0,
            drone_rotation: 0.0,
            sample_rate: 2,
            hover_delay: 5
            model: none
        }
        Detect task2 {
            way_points: [(-79.9497296, 40.415505, 25.0),(-79.9497001, 40.41507, 25.0)],
            gimbal_pitch: -45.0,
            drone_rotation: 0.0,
            sample_rate: 2,
            hover_delay: 5
            model: none
        }
    }
    
    Mission {
        Start { task1 }
        Transition (timeout(40)) task1 -> task2
    }


### Command Line Interface

After finish writing the mission script in DSL, user can parse the DSL to low level AST tree

Cmd

```
./gradlew :cli:run --args="../preprocess/src/main/resources/{DSL script you have written} --args"
```

Example of AST

```txt
FILE(0,898)
  WHITE_SPACE(0,8)
  TASK(8,788)
    TASK_KW(8,12)
    WHITE_SPACE(12,13)
    LBRACE(13,14)
    WHITE_SPACE(14,27)
    TASK_DECL(27,411)
     ....
    TASK_DECL(425,776)
    ....
      
  MISSION(799,898)
    MISSION_KW(799,806)
    WHITE_SPACE(806,807)
    LBRACE(807,808)
    WHITE_SPACE(808,821)
    MISSION_CONTENT(821,888)
     ....
    WHITE_SPACE(888,897)
    RBRACE(897,898)
```

convert low level AST to concrete level structure Flight Plan Structure (FPS):

- The FPS contains the a list of Task object, where each task object has its own task type(detect, track, object avoidance). Each task type contains different set of attribute informations needed for executing that task required for steel-eagle pipeline.

![img](https://documents.lucid.app/documents/036d65a8-1197-41e7-9e98-4f0be76c5665/pages/0_0?a=4430&x=370&y=2502&w=2797&h=1278&store=1&accept=image%2F*&auth=LCA%205cb2b0edcaf57679326235c98853fe27a98e634d74ca697f277a8583753e0b5f-ts%3D1701799469)



- Translate to state machine written in python or java:

  - The actual flight script contains three components: MissionRunner, TaskController, and TaskDefs

  - Mission Runner: define all the tasks, start the first task, and manage the task transition based on the decision made from Task Controller.

  - Task Controller: Manage a event queue. Once recieved an event in the event queue, make decision on what task should be run next based on the current task, and event message. Notify the Mission Runner to transit to the next task.

  - TaskDefs: This is the implementation of specific tasks including detect task, track task, and object avoidance task. These tasks are reponsible for sending the triggered event message to the task controller
  - The above three components completes a finite state machine for drone's flight mission

- Example of code generated(python)

  - **Mission Runner:**

    - ```python
      from dependencies.FlightScript import FlightScript
      # Import derived tasks
      from runtime.DetectTask import DetectTask
      import queue
      import time
      
      
      class MissionRunner(FlightScript):
          def __init__(self, drone):
              super().__init__(drone)
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
              kwargs["coords"] = "[{'lng': -79.95027, 'lat': 40.415672, 'alt': 25.0}, {'lng': -79.950264, 'lat': 40.41546, 'alt': 25.0}, {'lng': -79.94991, 'lat': 40.415455, 'alt': 25.0}, {'lng': -79.94991, 'lat': 40.415676, 'alt': 25.0}, {'lng': -79.95027, 'lat': 40.415672, 'alt': 25.0}]"
              self.task1 = DetectTask(self.drone, "task1", event_queue, **kwargs)
              self.taskMap["task1"] = self.task1
              # TASKtask2
              kwargs.clear()
              kwargs["gimbal_pitch"] = "-45.0"
              kwargs["drone_rotation"] = "0.0"
              kwargs["sample_rate"] = "2"
              kwargs["hover_delay"] = "0"
              kwargs["coords"] = "[{'lng': -79.949905, 'lat': 40.4153, 'alt': 25.0}, {'lng': -79.95023, 'lat': 40.4153, 'alt': 25.0}, {'lng': -79.95005, 'lat': 40.41511, 'alt': 25.0}, {'lng': -79.949905, 'lat': 40.4153, 'alt': 25.0}]"
              self.task2 = DetectTask(self.drone, "task2", event_queue, **kwargs)
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
             task_id = self.task1.get_task_id()
             self.set_current_task(task_id)
             print(f"MR: start mission, current taskid:{task_id}\n")
             # start
             self.taskQueue.put(self.task1)
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
      ```



- **Task Controller**:

  - ```python
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
      ```



- **TaskDefs:**

  - ```python
      import threading
      from dependencies.Task import Task
      import time
      import ast
      
      class DetectTask(Task):
      def __init__(self, drone, task_id, event_queue,**kwargs):
          super().__init__(drone, task_id, **kwargs)
          self.event_queue = event_queue
      
      def trigger_event(self, event):
          print(f"**************Detect Task {self.task_id}: triggered event! {event}**************\n")
          self.event_queue.put((self.task_id,  event))
      
      def run(self):
          # triggered event
          if (self.task_id == "task1"):
              # construct the timer with 90 seconds
              timer = threading.Timer(90, self.trigger_event, ["timeout"])
              timer.daemon = True
              # Start the timer
              timer.start()
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
      ```



### Post-process

In this module, users run the script generated from the CLI module. Currently, the automatic generated script supports the **Steel Eagle** pipeline.

Background of Steel Eagle:

Steel Eagle is separated into three distinct parts: the local commander client, the cloudlet server, and the on board software. The commander client is intended to run on a personal computer close to the PIC (Pilot in Command) with an Internet connection. It gives an interface to receive telemetry and upload an mission script to the drone. It also provides tools to assume manual control of the drone while it is in-flight (*kill* command). The cloudlet server is the bridge between the onboard drone software and the commander client. It relays messages between the two and also publicly hosts flight scripts. Additionally, the server runs compute engines for the drone which will be executed on the offloaded sensor data/video stream. Finally, the onboard device consists of onion router and drone. The router relays telemetry and offloads sensor data/video frames to the cloudlet server.

![img](https://documents.lucid.app/documents/523a70de-9a85-4a33-9ec7-c156c8f31f8c/pages/0_0?a=3428&x=309&y=1114&w=4181&h=1012&store=1&accept=image%2F*&auth=LCA%20d14269d13fd5623d6182fa1cb17cfc7f55d0a71379af3cf669149bea6a916fbd-ts%3D1701958462)

Simulation Environment setup:

- Parrot Simulation Environment:
  - Sphinx drone
  - parrot unity engine
  - Omlype SDK  environment
- Steel-eagle Pipeline:
  - Local commander client:
    - commander
  - On board device:
    - Drone
    - Onion Router
  - Cloud server
    - Gabriel Server
    - Cognitive Engines
    - supervisor

parrot cmd:

```
env:
    sphinx "/opt/parrot-sphinx/usr/share/sphinx/drones/anafi.drone"::firmware="https://firmware.parrot.com/Versions/anafi/pc/%23latest/images/anafi-pc.ext2.zip"

    parrot-ue4-sphx-tests -level=main -list-paths
    == Available Paths ===========================================
    Path name : DefaultPath
    Path name : LongPath
    Path name : SquarePath
    ==============================================================

    parrot-ue4-sphx-tests -gps-json='{"lat_deg":40.4156235, "lng_deg":-79.9504726 , "elevation":1.5}' -ams-path="DefaultPath,Pickup:*" -ams-path=SquarePath,Jasper

    sphinx-cli param -m world actors pause false
```



User supposed to zip the generated scripts and uploaded the compressed file to the web server for cloud server to download. Once uploaded, user can run the commander and send the run command to the cloud server. The cloud server will download the script and run it in the supervisor to start the mission plan.

The run time of the mission plan could be concluded as a finite state machine of flight mission. Drone start from the start state. And transit to the first task state and follow the drone command instructed in that state. During that task state, if there is any event triggered, the supervisor will transit the current state to another task state. The supervisor will move the drone to the done state whenever the drone finished all the commands in the current task state. The done state will make the drone to terminate its flight and return to home.

Below is an example of finite state machine that describe this mission in DSL:

```
Task {
    Detect task1 {
        way_points: [(-79.9503492, 40.4155806, 25.0),(-79.9491717, 40.4155826, 25.0)],
        gimbal_pitch: -45.0,
        drone_rotation: 0.0,
        sample_rate: 2,
        hover_delay: 5
        model: none
    }
    Detect task2 {
        way_points: [(-79.9497296, 40.415505, 25.0),(-79.9497001, 40.41507, 25.0)],
        gimbal_pitch: -45.0,
        drone_rotation: 0.0,
        sample_rate: 2,
        hover_delay: 5
        model: none
    }
}

Mission {
    Start { task1 }
    Transition (timeout(40)) task1 -> task2
}
```

In this case, there are two tasks. Task1 and task2. The drone will start off with the starting task which is task1 by executing its command. When the triggered event in this case "timeup" has occurred, the drone will transit from task 1 to task 2 as instructed in droneDSL. And if the drone finishes its task without transitioning to any other state. It will move to the done state and thereby meant to terminate the whole flight session.

- Finite State Machine example:

  <img src="https://documents.lucid.app/documents/036d65a8-1197-41e7-9e98-4f0be76c5665/pages/0_0?a=3833&x=2686&y=1284&w=1167&h=773&store=1&accept=image%2F*&auth=LCA%206f845b95e4708a274f9b232449aa8261fc407a956e3bbabc7715e7dc9446febc-ts%3D1701359926" alt="img" style="zoom:67%;" />





