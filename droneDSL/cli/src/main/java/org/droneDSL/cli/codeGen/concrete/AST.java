package org.droneDSL.cli.codeGen.concrete;

import kala.collection.immutable.ImmutableMap;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.Objects;
import java.util.function.Consumer;


public final class AST {
  private final ImmutableMap<String, Task> taskMap;
  private final boolean isSteelEagle;

  public String startTaskID;

  public AST(String startTaskID, ImmutableMap<String, Task> taskMap, boolean isSteelEagle) {
    this.startTaskID = startTaskID;
    this.taskMap = taskMap;
    this.isSteelEagle = isSteelEagle;
  }

  public void codeGenPython() throws IOException {
    var pRoot = Paths.get("../postprocess");
    if (!this.isSteelEagle) {
      var root = pRoot.resolve("task-switch/runtime");
      Files.createDirectories(root);
      Files.writeString(root.resolve("MissionRunner.py"), missionRunnerContent());
      Files.writeString(root.resolve("TaskController.py"), taskControllerContent());
      Files.writeString(root.resolve("DetectTask.py"), detectTaskContent());
    } else {
      var root = pRoot.resolve("python/runtime");
      Files.createDirectories(root);
      Files.writeString(root.resolve("MissionController.py"), missionControllerContent(), StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);
    }

  }

  private String missionControllerContent() {

    StringBuilder staticMethod = new StringBuilder();
    StringBuilder missionTrans = new StringBuilder();
    StringBuilder missionTask = new StringBuilder();

    staticMethod.append("""
            # transition
        """);

    missionTrans.append("""
            #task
            def define_mission(self):
            
                #define transition
                print("MissionController: define the transitMap\\n")
                        
        """);
    missionTask.append(String.format("""
                # define task
                print("MissionController: define the tasks\\n")
                self.start_task_id = "%s"
        """, this.startTaskID));


    taskMap.forEach((taskID, taskContent) -> {
      //task
      staticMethod.append(String.format("""
              @staticmethod
              def %s_transit(triggered_event):
          """, taskID));

      for (var trans: taskContent.transitions){
        staticMethod.append(String.format("""
                  if (triggered_event == "%s"):
                      return "%s"
          """, trans.condID(), trans.nextTaskID()));
      }


      missionTrans.append(String.format("""
                  self.transitMap["%s"]= self.%s_transit
          """, taskID, taskID));

      missionTask.append(taskContent.generateDefineTaskCode(this.isSteelEagle));



      staticMethod.append("""
                  if (triggered_event == "done"):
                      return "terminate"
                      
          """);
    });


    staticMethod.append("""
            @staticmethod
            def default_transit(triggered_event):
                print(f"MissionController: no matched up transition, triggered event {triggered_event}\\n", triggered_event)
        """);

    missionTrans.append("""
                self.transitMap["default"]= self.default_transit
        """);

    return
        """
            from task_defs.TrackTask import TrackTask
            from task_defs.DetectTask import DetectTask
            from runtime.MissionRunner import MissionRunner
            from enum import Enum
            import threading
            import queue
                        
                        
            class MissionController(threading.Thread):
                class TaskType(Enum):
                    Detect = 1
                    Track = 2
                        
                class TaskArguments():
                    def __init__(self, task_type, transitions_attributes, task_attributes):
                        self.task_type = task_type
                        self.task_attributes = task_attributes
                        self.transitions_attributes = transitions_attributes
                        
                        
                def __init__(self, drone, cloudlet):
                    super().__init__()
                    self.trigger_event_queue = queue.Queue()
                    self.drone = drone
                    self.cloudlet = cloudlet
                    self.start_task_id = None
                    self.transitMap = {}
                    self.task_arg_map = {}
            """ + staticMethod + missionTrans + missionTask+ """
                          
                def create_task(self, task_id):
                    if (task_id in self.task_arg_map.keys()):
                        if (self.task_arg_map[task_id].task_type == self.TaskType.Detect):
                            return DetectTask(self.drone, self.cloudlet, task_id, self.trigger_event_queue, self.task_arg_map[task_id])
                        elif (self.task_arg_map[task_id].task_type == self.TaskType.Track):
                            return TrackTask(self.drone, self.cloudlet, task_id, self.trigger_event_queue, self.task_arg_map[task_id])
                   \s
                    return None
                       \s
                def next_task(self, current_task_id, triggered_event):
                    next_task_id  = self.transitMap.get(current_task_id, self.default_transit)(triggered_event)
                    return next_task_id
                        
                def run(self):
                    # start the mc
                    print("MissionController: hi start the controller\\n")
                        
                    print("MissionController: define mission \\n")
                    self.define_mission()
                        
                    # init the mission runner
                    print("MissionController: init the mission runner\\n")
                    mr = MissionRunner(self.drone)
                   \s
                    mr.start()
                    start_task = self.create_task(self.start_task_id)
                    if start_task != None:
                        mr.start_mission(start_task)
                   \s
                        
                    # main logic check the triggered event
                    while True:
                        item = self.trigger_event_queue.get()
                        
                        if item is not None:
                            task_id = item[0]
                            trigger_event = item[1]
                            print(f"MissionController: Trigger one event! \\n")
                            print(f"MissionController: Task id  {task_id} \\n")
                            print(f"MissionController: event   {trigger_event} \\n")
                            if (task_id == mr.get_current_task()):
                                next_task_id = self.next_task(task_id, trigger_event)
                                if (next_task_id == "terminate"):
                                    break
                                else:
                                    next_task = self.create_task(next_task_id)
                                    mr.transit_to(next_task)
                        
                    # terminate the mr
                    print(f"MissionController: the current task is done, terminate the MISSION RUNNER \\n")
                    mr.end_mission()
                        
                    #end the mc
                    print("MissionController: terminate the controller\\n")
                        
                        
                        
                        



            """;
  }

  private String detectTaskContent() {

    StringBuilder triggerEvent = new StringBuilder("        # triggered event\n");

    taskMap.forEach((taskID, taskContent) -> {
      taskContent.transitions.forEach(transition -> {
        if (transition.condID().equals("timeout")) {
          triggerEvent.append(String.format("""
                      if (self.task_id == "%s"):
                          # construct the timer with %s seconds
                          timer = threading.Timer(%s, self.trigger_event, ["timeout"])
                          timer.daemon = True
                          # Start the timer
                          timer.start()
              """, taskID, transition.condArg(), transition.condArg()));
        }
      });
    });

    return """
               import threading
               from dependencies.Task import Task
               import time
               import ast
                       
               class DetectTask(Task):
                       
                   def __init__(self, drone, task_id, event_queue,**kwargs):
                       super().__init__(drone, task_id, **kwargs)
                       self.event_queue = event_queue
                  
                   def trigger_event(self, event):
                       print(f"**************Detect Task {self.task_id}: triggered event! {event}**************\\n")
                       self.event_queue.put((self.task_id,  event))
                       
                   def run(self):
                   """ + triggerEvent + """
                       try:
                           print(f"**************Detect Task {self.task_id}: hi this is detect task {self.task_id}**************\\n")
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

                           print(f"**************Detect Task {self.task_id}: Done**************\\n")
                           self.trigger_event("done")
                       except Exception as e:
                           print(e)
                       
                       
               """;
  }

  private String taskControllerContent() {


    StringBuilder transitionMap = new StringBuilder();
    StringBuilder staticMethod = new StringBuilder();

    transitionMap.append("        self.transitMap = {\n");

    taskMap.forEach((taskID, taskContent) -> {
      staticMethod.append(String.format("""
              @staticmethod
              def %s_transit(triggered_event):
          """, taskID));
      taskContent.transitions.forEach((tran) -> {
        staticMethod.append(String.format("""
                    if (triggered_event == "%s"):
                        return "%s"
                        
            """, tran.condID(), tran.nextTaskID()));
      });
      staticMethod.append(String.format("""
                  if (triggered_event == "done"):
                      return "terminate"
                      
          """));
      transitionMap.append(String.format("            \"%s\": self.%s_transit,\n", taskID, taskID));
    });

    transitionMap.append("            \"default\": self.default_transit\n");
    transitionMap.append("""
                }
                
        """);


    return """
               import threading
                       
                       
               class TaskController(threading.Thread):
                     
                  
                   def __init__(self, mr):
                       super().__init__()
                       self.mr = mr
                       self.event_queue = mr.event_queue
                       """ + transitionMap + staticMethod + """                                         
                   @staticmethod
                   def default_transit(triggered_event):
                       print(f"no matched up transition, triggered event {triggered_event}\\n", triggered_event)
                   def next_task(self, triggered_event):
                       current_task_id = self.mr.get_current_task()
                       next_task_id  = self.transitMap.get(current_task_id, self.default_transit)(triggered_event)
                       self.mr.transit_to(next_task_id)
                       return next_task_id
                   def run(self):
                       print("hi start the controller\\n")
                       # check the triggered event
                       while True:
                           item = self.event_queue.get()
                           if item is not None:
                               print(f"Controller: Trigger one event {item} \\n")
                               print(f"Controller: Task id  {item[0]} \\n")
                               print(f"Controller: event   {item[1]} \\n")
                               if (item[0] == self.mr.get_current_task()):
                                   next_task_id = self.next_task(item[1])
                                   if (next_task_id == "terminate"):
                                       print(f"Controller: the current task is done, terminate the controller \\n")
                                       break
                                             
               """;
  }


  private String missionRunnerContent() {

    StringBuilder initContent = new StringBuilder("""
            def __init__(self, drone):
                super().__init__(drone)
                self.curr_task_id = None
                self.taskMap = {}
                self.event_queue = queue.Queue()
        """);

    StringBuilder defineTaskContent = new StringBuilder();

    String startMissionContent = """
            def start_mission(self):
               # set the current task
               task_id = self.%s.get_task_id()
               self.set_current_task(task_id)
               print(f"MR: start mission, current taskid:{task_id}\\n")
               # start
               self.taskQueue.put(self.%s)
               print("MR: taking off")
               self.drone.takeOff()
               self._execLoop()
        """.formatted(startTaskID, startTaskID);

    taskMap.forEach((taskID, taskContent) -> {
      // Example of what you might want to append
      initContent.append(String.format("        self.%s = None\n", taskID));
      defineTaskContent.append(taskContent.generateDefineTaskCode(this.isSteelEagle));
    });

    return
        """
            from dependencies.FlightScript import FlightScript
            # Import derived tasks
            from runtime.DetectTask import DetectTask
            import queue
            import time
                    
                    
            class MissionRunner(FlightScript):
              """ + initContent + """
                def define_task(self, event_queue):
                    # Define task
                    kwargs = {}
            """ + defineTaskContent + """
                def transit_to(self, task_id):
                    print(f"MR: transit to task with task_id: {task_id}, current_task_id: {self.curr_task_id}")
                    self.set_current_task(task_id)
                    self._kill()
                    if (task_id != "terminate"):
                        self._push_task(self.taskMap[task_id])
                        self._execLoop()
                    else:
                        self.end_mission()
            """ + startMissionContent + """
                def end_mission(self):
                    print("MR: end mission, rth\\n")
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
                        print("MR: define the tasks\\n")
                        self.define_task(self.event_queue)
                        # start mission
                        print("MR: start the mission!\\n")
                        self.start_mission()
                    except Exception as e:
                        print(e)
            """;
  }

  public ImmutableMap<String, Task> taskMap() {
    return taskMap;
  }

  @Override
  public boolean equals(Object obj) {
    if (obj == this) return true;
    if (obj == null || obj.getClass() != this.getClass()) return false;
    var that = (AST) obj;
    return Objects.equals(this.taskMap, that.taskMap);
  }

  @Override
  public int hashCode() {
    return Objects.hash(taskMap);
  }

  @Override
  public String toString() {
    return "AST[" +
           "taskMap=" + taskMap + ']';
  }
}
