package org.droneDSL.cli.codeGen.concrete;

import kala.collection.immutable.ImmutableSeq;

public class DetectTask extends Task {
  public float gimbalPitch;
  public float droneRotation;
  public int sampleRate;
  public int hoverDelay;
  public String model;

  public ImmutableSeq<Point> wayPoints;

  public record Point(double x, double y, double z) {
    public String toJson() {
      return String.format("{'lng': %s, 'lat': %s, 'alt': %s}", x, y, z);
    }
  }

  public DetectTask(String taskID, ImmutableSeq<Point> wayPoints, float gimbalPitch, float droneRotation, int sampleRate, int hoverDelay, String model) {
    super(taskID);
    this.wayPoints = wayPoints;
    this.gimbalPitch = gimbalPitch;
    this.droneRotation = droneRotation;
    this.sampleRate = sampleRate;
    this.hoverDelay = hoverDelay;
    this.model = model;
  }

  public void debugPrint() {
    System.out.println("gimbal_pitch :" + gimbalPitch);
    System.out.println("drone_rotation :" + droneRotation);
    System.out.println("sample_rate :" + sampleRate);
    System.out.println("hover_delay :" + hoverDelay);
    System.out.println("model :" + model);
  }

  @Override
  public String generateDefineTaskCode(boolean isSteelEagle) {
    var waypointsStr = wayPoints.joinToString(",", "[", "]", Point::toJson);
    if (!isSteelEagle) {
      return """
                  # TASK%s
                  kwargs.clear()
                  kwargs["gimbal_pitch"] = "%s"
                  kwargs["drone_rotation"] = "%s"
                  kwargs["sample_rate"] = "%s"
                  kwargs["hover_delay"] = "%s"
                  kwargs["coords"] = "%s"
                  self.%s = DetectTask(self.drone, "%s", event_queue, **kwargs)
                  self.taskMap["%s"] = self.%s
          """.formatted(taskID, gimbalPitch, droneRotation, sampleRate, hoverDelay, waypointsStr, taskID, taskID, taskID, taskID);
    } else {

      return """
                  # TASK%s
                  task_attr_%s = {}
                  task_attr_%s["gimbal_pitch"] = "%s"
                  task_attr_%s["drone_rotation"] = "%s"
                  task_attr_%s["sample_rate"] = "%s"
                  task_attr_%s["hover_delay"] = "%s"
                  task_attr_%s["coords"] = "%s"
                  task_attr_%s["model"] = "%s"
          """.formatted(taskID, taskID, taskID, gimbalPitch, taskID, droneRotation, taskID, sampleRate, taskID, hoverDelay, taskID, waypointsStr, taskID, model)
             + this.generateTaskTransCode() +
             """
                   self.task_arg_map["%s"] = self.TaskArguments(self.TaskType.Detect, transition_attr_%s, task_attr_%s)
           """.formatted(taskID, taskID, taskID);

    }
  }


}
