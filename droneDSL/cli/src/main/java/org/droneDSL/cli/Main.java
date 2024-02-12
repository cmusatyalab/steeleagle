package org.droneDSL.cli;

import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import kala.collection.immutable.ImmutableMap;
import org.droneDSL.cli.codeGen.concrete.AST;
import org.droneDSL.cli.codeGen.concrete.Preparse;
import org.droneDSL.cli.codeGen.concrete.Task;
import org.droneDSL.cli.codeGen.pythonGen.CodeGeneratorPython;
import org.droneDSL.cli.parser.BotPsiElementTypes;
import org.jetbrains.annotations.NotNull;
import org.droneDSL.cli.psi.DslParserImpl;
import org.droneDSL.cli.psi.StreamReporter;

import java.io.FileNotFoundException;
import java.io.FileReader;
import java.io.IOException;
import java.io.Serializable;
import java.lang.reflect.Type;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public class Main {
  public static void main(String[] args) throws FileNotFoundException {
    String filePath = args[0];
    boolean isSteelEagle = Objects.equals(args[1], "--se");
    String fileContent;

    try {
      // Read the content of the file
      fileContent = Files.readString(Paths.get(filePath));
    } catch (IOException e) {
      System.err.println("Error reading the file: " + e.getMessage());
      return; // Exit if there's an error reading the file
    }

    var node = parser().parseNode(fileContent);
    System.out.println(node.toDebugString());


    var waypointsMap = readFromSharedDir();
    ImmutableMap<String, Task> taskMap = ImmutableMap.from(node.child(BotPsiElementTypes.TASK).childrenOfType(BotPsiElementTypes.TASK_DECL)
        .map(task -> Preparse.createTask(task, waypointsMap)));
    var startTaskID = Preparse.createMission(node.child(BotPsiElementTypes.MISSION).child(BotPsiElementTypes.MISSION_CONTENT), taskMap);


    var ast = new AST(startTaskID, taskMap, isSteelEagle);

    CodeGeneratorPython.generateCode(ast);
  }

  @NotNull
  private static DslParserImpl parser() {
    return new DslParserImpl(new StreamReporter(System.out));
  }

  public record Pt(
      String longitude,
      String latitude,
      String altitude
  ) implements Serializable {
  }

  @NotNull
  private static Map<String, List<Pt>> readFromSharedDir() throws FileNotFoundException {
    // Read JSON from file
    FileReader reader = new FileReader("../shared_dir/coordinates.json");
    Type type = new TypeToken<Map<String, List<Pt>>>() {
    }.getType();
    Gson gson = new Gson();
    return gson.fromJson(reader, type);
  }
}
