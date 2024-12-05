package org.droneDSL.compile.codeGen.concrete;

import kala.collection.immutable.ImmutableSeq;

public class TestTask extends Task {


  public TestTask(String taskID, ImmutableSeq<Point> wayPoints) {
    super(taskID);
    this.wayPoints = wayPoints;
  }

  @Override
  public void debugPrint() {
    System.out.println("Test Task no attribute!");
  }

  @Override
  public String generateDefineTaskCode() {
    var waypointsStr = wayPoints.joinToString(",", "[", "]", Point::toJson);
    return """
                # TASK%s
                task_attr_%s = {}
                task_attr_%s["coords"] = "%s"
        """.formatted(taskID, taskID, taskID, waypointsStr)
           + this.generateTaskTransCode() +
           """
                 task_arg_map["%s"] = TaskArguments(TaskType.Test, transition_attr_%s, task_attr_%s)
         """.formatted(taskID, taskID, taskID);
  }
}
