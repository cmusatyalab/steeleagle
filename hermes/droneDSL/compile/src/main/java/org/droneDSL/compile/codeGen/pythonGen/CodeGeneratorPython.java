package org.droneDSL.compile.codeGen.pythonGen;

import org.droneDSL.compile.codeGen.concrete.MissionPlan;

import java.io.IOException;

public class CodeGeneratorPython {
  public static void generateCode(MissionPlan missionPlan) {
    try {

      missionPlan.codeGenPython();


    } catch (IOException e) {
      e.printStackTrace();
    }
  }
}
