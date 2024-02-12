package org.droneDSL.cli.codeGen.concrete;

import kala.collection.immutable.ImmutableSeq;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;

import java.util.ArrayList;
import java.util.List;

public abstract class Task {

  public String taskID;

  public Task(String taskID) {
    this.taskID = taskID;
    this.transitions = new ArrayList<>();
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

  public abstract String generateDefineTaskCode(boolean isSteelEagle);

  public String generateTaskTransCode() {
    var transitCode = new StringBuilder();
    transitCode.append(String.format(
        """
                transition_attr_%s = {}
        """, taskID));

    for (var trans : this.transitions){

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
