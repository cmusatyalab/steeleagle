package org.droneDSL.cli.codeGen.concrete;

import kala.collection.Seq;
import kala.collection.immutable.ImmutableMap;
import kala.collection.immutable.ImmutableSeq;
import kala.collection.mutable.MutableMap;
import kala.text.StringSlice;
import kala.tuple.Tuple;
import kala.tuple.Tuple2;
import org.aya.intellij.GenericNode;
import org.droneDSL.cli.Main;
import org.droneDSL.cli.parser.BotPsiElementTypes;
import org.jetbrains.annotations.NotNull;

import java.util.List;
import java.util.Map;

public interface Preparse {
  enum TaskKind {
    Detect,
    Track
  }

  class AttributeMap {
    MutableMap<StringSlice, GenericNode<? extends GenericNode<?>>> content = MutableMap.create();
    TaskKind kind;

    public GenericNode<? extends GenericNode<?>> get(String name) {
      return content.get(StringSlice.of(name));
    }
  }

  @NotNull
  static Tuple2<String, Task> createTask(GenericNode<? extends GenericNode<?>> task, Map<String, List<Main.Pt>> waypointsMap) {
    var attrMap = createMap(task);
    var taskID = task.child(BotPsiElementTypes.TASK_NAME).tokenText().toString();
    return switch (attrMap.kind) {
      case Detect -> {
        var gimbal_pitch = attrMap.get("gimbal_pitch").child(BotPsiElementTypes.NUMBER).tokenText();
        var drone_rotation = attrMap.get("drone_rotation").child(BotPsiElementTypes.NUMBER).tokenText();
        var sample_rate = attrMap.get("sample_rate").child(BotPsiElementTypes.NUMBER).tokenText();
        var hover_delay = attrMap.get("hover_delay").child(BotPsiElementTypes.NUMBER).tokenText();
        var model = attrMap.get("model").child(BotPsiElementTypes.NAME).tokenText();

        // waypoints
        var isWayPointsVar = attrMap.get("way_points").peekChild(BotPsiElementTypes.ANGLE_BRACKED);
        ImmutableSeq<DetectTask.Point> wayPoints;
        if (isWayPointsVar == null) {
          wayPoints = attrMap.get("way_points").child(BotPsiElementTypes.SQUARE_BRACKED).childrenOfType(BotPsiElementTypes.PAREN).
              map(point -> {
                var nums = point.child(BotPsiElementTypes.WAYPOINT).childrenOfType(BotPsiElementTypes.NUMBER)
                    .map(t -> t.tokenText().toFloat())
                    .toImmutableSeq();
                return new DetectTask.Point(nums.get(0), nums.get(1), nums.get(2));
              })
              .toImmutableSeq();
        } else {
          var wayPointsID = attrMap.get("way_points").child(BotPsiElementTypes.ANGLE_BRACKED).child(BotPsiElementTypes.NAME).tokenText().toString();
          wayPoints = Seq.wrapJava(waypointsMap.get(wayPointsID))
              .map(pt -> new DetectTask.Point(Double.parseDouble(pt.longitude()), Double.parseDouble(pt.latitude()), Double.parseDouble(pt.altitude())));
        }

        // construct new task
        var detectTask = new DetectTask(
            taskID,
            wayPoints,
            gimbal_pitch.toFloat(),
            drone_rotation.toFloat(),
            sample_rate.toInt(),
            hover_delay.toInt(),
            model.toString()
        );
        yield Tuple.of(taskID, detectTask);
      }
      case Track -> {
        var gimbal_pitch = attrMap.get("gimbal_pitch").child(BotPsiElementTypes.NUMBER).tokenText();
        var model = attrMap.get("model").child(BotPsiElementTypes.NAME).tokenText();
        var target_class = attrMap.get("class").child(BotPsiElementTypes.NAME).tokenText();

        // construct new task
        var trackTask = new TrackTask(
            taskID,
            gimbal_pitch.toFloat(),
            target_class.toString(),
            model.toString()
        );
        yield Tuple.of(taskID, trackTask);
      }

    };
  }

  static String createMission(GenericNode<? extends GenericNode<?>> missionContent, ImmutableMap<String, Task> taskMap) {

    var startTaskID = missionContent.child(BotPsiElementTypes.MISSION_START_DECL).child(BotPsiElementTypes.TASK_NAME).tokenText().toString();

    for (var transition : missionContent.childrenOfType(BotPsiElementTypes.MISSION_TRANSITION)) {
      var cond = transition.child(BotPsiElementTypes.PAREN).child(BotPsiElementTypes.COND);
      var condId = cond.child(BotPsiElementTypes.ID).tokenText().toString();
      var argNode = cond.peekChild(BotPsiElementTypes.PAREN);
      var taskPair = transition.childrenOfType(BotPsiElementTypes.TASK_NAME)
          .map(GenericNode::tokenText)
          .map(StringSlice::toString)
          .toImmutableSeq();
      var curr_task = taskPair.get(0);
      var next_task = taskPair.get(1);

      if (argNode != null) {
        var isArgID = argNode.peekChild(BotPsiElementTypes.ID);
        if (isArgID != null) {
          var arg = argNode.child(BotPsiElementTypes.ID).tokenText().toString();
          var tran = new Task.Transition<String>(condId, arg, curr_task, next_task);
          taskMap.get(curr_task).transitions.add(tran);
        } else {
          var arg = argNode.child(BotPsiElementTypes.NUMBER).tokenText().toDouble();
          var tran = new Task.Transition<Double>(condId, arg, curr_task, next_task);
          taskMap.get(curr_task).transitions.add(tran);

        }
      }

    }

    return startTaskID;
  }

  @NotNull
  private static AttributeMap createMap(GenericNode<? extends GenericNode<?>> task) {
    var isDetect = task.peekChild(BotPsiElementTypes.TASK_DETECT_KW);
    var attrMap = new AttributeMap();
    task.child(BotPsiElementTypes.TASK_BODY).childrenOfType(BotPsiElementTypes.ATTRIBUTE)
        .forEach(attr -> attrMap.content.put(attr.child(BotPsiElementTypes.ID).tokenText(), attr.child(BotPsiElementTypes.ATTRIBUTE_EXPR)));
    if (isDetect != null) {
      attrMap.kind = TaskKind.Detect;
    } else {
      attrMap.kind = TaskKind.Track;
    }
    return attrMap;
  }


}
