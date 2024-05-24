package org.droneDSL.compile.codeGen.concrete;

public class TrackTask extends Task {
  public float gimbalPitch;

  public String target_class;
  public String model;

  public HSV lowerBound;
  public HSV upperBound;


  public TrackTask(String taskID, float gimbalPitch, String target_class, String model, HSV lower_bound, HSV upper_bound) {
    super(taskID);
    this.gimbalPitch = gimbalPitch;
    this.model = model;
    this.target_class = target_class;
    this.lowerBound = lower_bound;
    this.upperBound = upper_bound;
  }

  @Override
  public void debugPrint() {
    System.out.println("gimbal_pitch :" + gimbalPitch);
    System.out.println("model :" + model);
    System.out.println("target_class :" + target_class);
    System.out.println("hsv (lower_bound/upper_bound) :" + this.lowerBound + " / " + this.upperBound);
  }

  @Override
  public String generateDefineTaskCode() {
    return """
                #TASK%s
                task_attr_%s = {}
                task_attr_%s["model"] = "%s"
                task_attr_%s["class"] = "%s"
                task_attr_%s["gimbal_pitch"] = "%s"
                task_attr_%s["upper_bound"] = %s
                task_attr_%s["lower_bound"] = %s
        """.formatted(taskID, taskID, taskID, model, taskID, target_class, taskID, gimbalPitch, taskID, upperBound.toString(), taskID, lowerBound.toString())
            + this.generateTaskTransCode() +
            """
                  task_arg_map["%s"] = TaskArguments(TaskType.Track, transition_attr_%s, task_attr_%s)
          """.formatted(taskID, taskID, taskID);
  }
}
