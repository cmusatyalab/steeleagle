package org.droneDSL.cli.codeGen.pythonGen;

import org.droneDSL.cli.codeGen.concrete.AST;

import java.io.IOException;

public class CodeGeneratorPython {
  public static void generateCode(AST ast) {
    try {

      ast.codeGenPython();


    } catch (IOException e) {
      e.printStackTrace();
    }
  }
}
