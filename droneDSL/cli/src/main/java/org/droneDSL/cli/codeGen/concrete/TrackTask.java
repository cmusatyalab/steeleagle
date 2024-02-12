package org.droneDSL.cli.codeGen.concrete;

import kala.collection.immutable.ImmutableSeq;

public class TrackTask extends Task {
  public float gimbalPitch;

  public String target_class;
  public String model;

  public TrackTask(String taskID, float gimbalPitch, String target_class, String model) {
    super(taskID);
    this.gimbalPitch = gimbalPitch;
    this.model = model;
    this.target_class = target_class;
  }

  public void debugPrint() {
    System.out.println("gimbal_pitch :" + gimbalPitch);
    System.out.println("model :" + model);
    System.out.println("target_class :" + target_class);
  }

  @Override
  public String generateDefineTaskCode(boolean isSteelEagle) {
    if (!isSteelEagle) {
      return "to be determined;" ;
    } else {

      return """
                  #TASK%s
                  task_attr_%s = {}
                  task_attr_%s["model"] = "%s"
                  task_attr_%s["class"] = "%s"
                  task_attr_%s["gimbal_pitch"] = "%s"
          """.formatted(taskID, taskID, taskID, model, taskID, target_class, taskID, gimbalPitch)
             + this.generateTaskTransCode() +
             """
                   self.task_arg_map["%s"] = self.TaskArguments(self.TaskType.Track, transition_attr_%s, task_attr_%s)
           """.formatted(taskID, taskID, taskID);

    }
  }



}
