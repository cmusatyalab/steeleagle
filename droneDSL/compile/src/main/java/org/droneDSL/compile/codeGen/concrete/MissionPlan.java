package org.droneDSL.compile.codeGen.concrete;

import kala.collection.immutable.ImmutableMap;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.Objects;


public final class MissionPlan {
  private final ImmutableMap<String, Task> taskMap;

  public String startTaskID;

  public MissionPlan(String startTaskID, ImmutableMap<String, Task> taskMap) {
    this.startTaskID = startTaskID;
    this.taskMap = taskMap;
  }

  public void codeGenPython(String rootPath) throws IOException {
    var root = Paths.get(rootPath);
    Files.writeString(root.resolve("Mission.py"), missionContent(), StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);
  }

  private String missionContent() {

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
                logger.info("define the transitMap\\n")
                transitMap["start"] = Mission.start_transit  
        """);
    missionTask.append(String.format("""
                # define task
                logger.info("define the tasks\\n")
        """, this.startTaskID));


    taskMap.forEach((taskID, taskContent) -> {

      var isDoneCustomized = false;

      //task
      staticMethod.append(String.format("""
              @staticmethod
              def %s_transit(triggered_event):
          """, taskID));

      for (var trans: taskContent.transitions){
        if (Objects.equals(trans.condID(), "done")){
          isDoneCustomized = true;
        }
        staticMethod.append(String.format("""
                  if (triggered_event == "%s"):
                      return "%s"
          """, trans.condID(), trans.nextTaskID()));
      }


      missionTrans.append(String.format("""
                  transitMap["%s"]= Mission.%s_transit
          """, taskID, taskID));

      missionTask.append(taskContent.generateDefineTaskCode());

      if (!isDoneCustomized){
        staticMethod.append("""
                  if (triggered_event == "done"):
                      return "terminate"
                      
          """);
      }
    });

    missionTask.append(String.format("""
                logger.info("finish defining the tasks\\n")
        """));


    staticMethod.append("""
            @staticmethod
            def default_transit(triggered_event):
                logger.info(f"no matched up transition, triggered event {triggered_event}\\n", triggered_event)
        """);

    missionTrans.append("""
                transitMap["default"]= Mission.default_transit
        """);

    return
        """
            import logging
            logger = logging.getLogger(__name__)
            logger.setLevel(logging.INFO)
            from interface.Task import TaskArguments, TaskType
                        
                        
            class Mission:

            """ + staticMethod + missionTrans + missionTask;
  }

  @Override
  public boolean equals(Object obj) {
    if (obj == this) return true;
    if (obj == null || obj.getClass() != this.getClass()) return false;
    var that = (MissionPlan) obj;
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
