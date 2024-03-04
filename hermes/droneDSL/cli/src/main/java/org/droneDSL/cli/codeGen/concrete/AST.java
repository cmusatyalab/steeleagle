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

  public String startTaskID;

  public AST(String startTaskID, ImmutableMap<String, Task> taskMap) {
    this.startTaskID = startTaskID;
    this.taskMap = taskMap;
  }

  public void codeGenPython() throws IOException {
    var pRoot = Paths.get("../postprocess");
    var root = pRoot.resolve("mission");
    Files.createDirectories(Files.readSymbolicLink(root));
    Files.writeString(root.resolve("MissionCreator.py"), missionControllerContent(), StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);


  }

  private String missionControllerContent() {

    StringBuilder staticMethod = new StringBuilder();
    StringBuilder missionTrans = new StringBuilder();
    StringBuilder missionTask = new StringBuilder();

    staticMethod.append(String.format("""
            # transition
            @staticmethod
            def start_transit(triggered_event):
                logger.info("start_transit\\n")
                return "%s"
        """, this.startTaskID));

    missionTrans.append("""
            #task
            @staticmethod
            def define_mission(transitMap, task_arg_map):
                #define transition
                logger.info("MissionController: define the transitMap\\n")
                transitMap["start"] = MissionCreator.start_transit        
        """);
    missionTask.append(String.format("""
                # define task
                logger.info("MissionController: define the tasks\\n")
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
                  transitMap["%s"]= MissionCreator.%s_transit
          """, taskID, taskID));

      missionTask.append(taskContent.generateDefineTaskCode());


      staticMethod.append("""
                  if (triggered_event == "done"):
                      return "terminate"
                      
          """);
    });


    staticMethod.append("""
            @staticmethod
            def default_transit(triggered_event):
                logger.info(f"MissionController: no matched up transition, triggered event {triggered_event}\\n", triggered_event)
        """);

    missionTrans.append("""
                transitMap["default"]= MissionCreator.default_transit
        """);

    return
        """
            import logging
            logger = logging.getLogger(__name__)
            logger.setLevel(logging.INFO)
            from interfaces.Task import TaskArguments, TaskType
                        
                        
            class MissionCreator:

            """ + staticMethod + missionTrans + missionTask;
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
