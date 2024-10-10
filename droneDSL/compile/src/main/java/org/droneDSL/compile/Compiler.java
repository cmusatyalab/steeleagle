package org.droneDSL.compile;

import kala.collection.immutable.ImmutableMap;
import org.droneDSL.compile.codeGen.concrete.MissionPlan;
import org.droneDSL.compile.codeGen.concrete.Parse;
import org.droneDSL.compile.codeGen.concrete.Task;
import org.droneDSL.compile.parser.BotPsiElementTypes;
import org.jetbrains.annotations.NotNull;
import org.droneDSL.compile.psi.DslParserImpl;
import org.droneDSL.compile.psi.StreamReporter;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;
import picocli.CommandLine;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

@CommandLine.Command(name = "DroneDSL Compiler", version = "DroneDSL Compiler 1.0", mixinStandardHelpOptions = true)
public class Compiler implements Runnable {
  public record Pt(@NotNull String longitude, @NotNull String latitude, @NotNull String altitude) {
  }

  @CommandLine.Option(names = {"-k", "--kmlFilePath"}, paramLabel = "<kmlFilePath>", defaultValue = "", description = "File Path of the KML file")
  String kmlFilePath;

  @CommandLine.Option(names = {"-d", "--dslFilePath"}, paramLabel = "<dslFilePath>", defaultValue = "null", description = "File Path of the DSL script")
  String dslFilePath;

  @CommandLine.Option(names = {"-o", "--outputFilePath"}, paramLabel = "<outputFilePath>", defaultValue = "./flightplan.ms", description = "output file path")
  String outputFilePath = "./flightplan.ms";

  @CommandLine.Option(names = {"-a", "--altitude"}, paramLabel = "<altitude>", defaultValue = "15", description = "altitude of the waypoints specified")
  String altitude = "15";

  @CommandLine.Option(names = {"-p", "--platform"}, paramLabel = "<platform>", defaultValue = "python/user/project", description = "compiled code platform")
  String platform = "python/user/project";

  @Override
  public void run() {
    // preprocess
    Map<String, List<Compiler.Pt>> waypointsMap;
    if (!kmlFilePath.isEmpty()) {
      // Parse the KML file if kmlFilePath is provided
      waypointsMap = parseKML2Map(kmlFilePath, altitude);
    } else {
      // Initialize an empty map or provide default values if kmlFilePath is not provided
      waypointsMap = new HashMap<>();
      System.out.println("No KML file provided. Proceeding without waypoints.");
    }

    // get the DSL script file
    String fileContent;
    try {
      fileContent = Files.readString(Paths.get(dslFilePath));
    } catch (IOException e) {
      System.err.println("Error reading the file: " + e.getMessage());
      return;
    }

    // get the ast
    var node = parser().parseNode(fileContent);
    System.out.println(node.toDebugString());

    // get the concrete Flight plan structure
    ImmutableMap<String, Task> taskMap = ImmutableMap.from(node.child(BotPsiElementTypes.TASK).childrenOfType(BotPsiElementTypes.TASK_DECL).map(task -> Parse.createTask(task, waypointsMap)));
    var startTaskID = Parse.createMission(node.child(BotPsiElementTypes.MISSION).child(BotPsiElementTypes.MISSION_CONTENT), taskMap);
    var ast = new MissionPlan(startTaskID, taskMap);

    // code generate
    var platformPath = String.format("./%s", platform);
    System.out.println(platformPath);
    try {
      ast.codeGenPython(platformPath);
    } catch (IOException e) {
      e.printStackTrace();
    }

    // build file generate
    try {
      ProcessBuilder builder = new ProcessBuilder();
      var cmd = String.format("cd %s/implementation && pipreqs . --force", platform);
      builder.command("bash", "-c", cmd);
  
      Process process = builder.start();
      int exitCode = process.waitFor(); // Wait for the command to complete
  
      if (exitCode != 0) {
          System.err.println("Error: pipreqs command failed with exit code " + exitCode);
          // Optionally, capture and print the error output from the process
          try (Scanner scanner = new Scanner(process.getErrorStream()).useDelimiter("\\A")) {
              String errorOutput = scanner.hasNext() ? scanner.next() : "No error output.";
              System.err.println("Error Output: " + errorOutput);
          }
      } else {
          System.out.println("pipreqs command executed successfully.");
      }
  } catch (IOException | InterruptedException e) {
      e.printStackTrace();
  }

    // zip
    try {
      FileOutputStream fos = new FileOutputStream(outputFilePath);
      ZipOutputStream zos = new ZipOutputStream(fos);

      // add directory's files to the zip
      addToZipFile(platformPath + "/implementation", "", zos);
      // Add task_defs to the zip
      addToZipFile(platformPath + "/implementation/task_defs", "/task_defs", zos);

      // Add transition_defs to the zip
      addToZipFile(platformPath + "/implementation/transition_defs", "/transition_defs", zos);

      zos.close();
      fos.close();
    } catch (IOException e) {
      e.printStackTrace();
    }
  }

  public void runWithArguments(String dslFilePath, String outputFilePath, String kmlFilePath, String altitude, String platform) {
    this.dslFilePath = dslFilePath;
    this.outputFilePath = outputFilePath;
    this.kmlFilePath = kmlFilePath;
    this.altitude = altitude;
    this.platform = platform;
    run();  // Call the main `run` method to perform the actual work  
  }

  public static void main(String[] args) {
    int exitCode = new CommandLine(new Compiler()).execute(args);
    System.exit(exitCode);
  }

  @NotNull
  private static DslParserImpl parser() {
    return new DslParserImpl(new StreamReporter(System.out));
  }

  private static void addToZipFile(String sourceDir, String insideZipDir, ZipOutputStream zos) throws IOException {
    File dir = new File(sourceDir);
    File[] files = dir.listFiles();
    if (files != null) {
      for (File file : files) {
        if (file.isFile()) {
          zos.putNextEntry(new ZipEntry(insideZipDir + "/" + file.getName()));
          Files.copy(file.toPath(), zos);
          zos.closeEntry();
        }
      }
    }
  }

  private static Map<String, List<Compiler.Pt>> parseKML2Map(String kmlPath, String altitude) {
    Map<String, List<Compiler.Pt>> coordinatesMap = new HashMap<>();
    try {
      DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
      DocumentBuilder builder = factory.newDocumentBuilder();
      Scanner scanner = new Scanner(System.in);

      // Replace this with your KML file path or an InputStream
      Document document = builder.parse(kmlPath);
      NodeList placemarks = document.getElementsByTagName("Placemark");

      // build the map
      for (int i = 0; i < placemarks.getLength(); i++) {
        Node placemark = placemarks.item(i);
        if (placemark.getNodeType() == Node.ELEMENT_NODE) {

          Element placemarkElement = (Element) placemark;
          String name = placemarkElement.getElementsByTagName("name").item(0).getTextContent();
          NodeList coordinateList = placemarkElement.getElementsByTagName("coordinates");
          String[] coordinates = coordinateList.item(0).getTextContent().trim().split("\\s+");
          List<Compiler.Pt> coords = new ArrayList<>();

          for (String coordinate : coordinates) {
            String[] coordinate_ele = coordinate.split(",");
            if (coordinate_ele.length >= 2) { // Making sure there are at least longitude and latitude
              String longitude = coordinate_ele[0];
              String latitude = coordinate_ele[1];
              var pt = new Pt(longitude, latitude, altitude);
              coords.add(pt);
            }
            coordinatesMap.put(name, coords);
          }

        }
      }

      // Example of retrieving data
      for (var entry : coordinatesMap.entrySet()) {
        System.out.println("Name: " + entry.getKey() + " - Coordinates: " + entry.getValue());
      }

      scanner.close();

    } catch (Exception e) {
      e.printStackTrace();
    }
    return coordinatesMap;
  }
}
