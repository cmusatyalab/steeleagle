package org.droneDSL.compile.codeGen.concrete;

import kala.collection.immutable.ImmutableSeq;

public class AvoidTask extends Task {
  public float speed;
  public String model;

  public AvoidTask(String taskID, ImmutableSeq<Point> wayPoints, float speed, String model) {
    super(taskID);
    this.wayPoints = wayPoints;
    this.speed = speed;
    this.model = model;
  }

  @Override
  public void debugPrint() {
    System.out.println("speed :" + speed);
    System.out.println("model :" + model);
  }

  @Override
  public String generateDefineTaskCode() {
    var waypointsStr = wayPoints.joinToString(",", "[", "]", Point::toJson);
    return """
                # TASK%s
                task_attr_%s = {}
                task_attr_%s["speed"] = "%s"
                task_attr_%s["model"] = "%s"
                task_attr_%s["coords"] = "%s"
        """.formatted(taskID, taskID, taskID, speed, taskID, model, taskID, waypointsStr)
           + this.generateTaskTransCode() +
           """
                 task_arg_map["%s"] = TaskArguments(TaskType.Avoid, transition_attr_%s, task_attr_%s)
         """.formatted(taskID, taskID, taskID);
  }
}
