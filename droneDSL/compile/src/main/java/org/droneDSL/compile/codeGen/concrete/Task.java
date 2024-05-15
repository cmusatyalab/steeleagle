package org.droneDSL.compile.codeGen.concrete;

import kala.collection.immutable.ImmutableSeq;
import org.jetbrains.annotations.Nullable;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

public abstract class Task {

  public String taskID;

  public Task(String taskID) {
    this.taskID = taskID;
    this.transitions = new ArrayList<>();
  }


  public ImmutableSeq<Point> wayPoints;
  public record Point(double x, double y, double z) {
    public String toJson() {
      return String.format("{'lng': %s, 'lat': %s, 'alt': %s}", x, y, z);
    }
  }
  public record HSV(int h, int s, int v) {
    public String toString() {
      return String.format("[%s, %s, %s]", h, s, v);
    }
  }

  public List<Transition> transitions;
  public record Transition<T>(
      String condID,
      @Nullable T condArg,
      String currentTaskID,
      String nextTaskID
  ) {
  }



  public abstract void debugPrint();

  public abstract String generateDefineTaskCode();

  public String generateTaskTransCode() {
    var transitCode = new StringBuilder();
    transitCode.append(String.format(
        """
                transition_attr_%s = {}
        """, taskID));

    for (var trans : this.transitions){
      if (Objects.equals(trans.condID, "done")){
        continue;
      }
      if (trans.condArg() instanceof String){
        transitCode.append(String.format(
            """
                    transition_attr_%s["%s"] = "%s"
            """, taskID, trans.condID(), trans.condArg()));
      } else{ // number
        transitCode.append(String.format(
            """
                    transition_attr_%s["%s"] = %s
            """, taskID, trans.condID(), trans.condArg()));
      }
    }
    return transitCode.toString();
  }
}
