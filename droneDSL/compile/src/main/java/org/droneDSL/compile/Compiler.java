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
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

@CommandLine.Command(name = "DroneDSL Compiler", version = "DroneDSL Compiler 1.0", mixinStandardHelpOptions = true)
public class Compiler implements Runnable {
  public record Pt(@NotNull String longitude, @NotNull String latitude, @NotNull String altitude) {
  }

  @CommandLine.Option(names = {"-k", "--kmlFilePath"}, paramLabel = "<kmlFilePath>", defaultValue = "null", description = "File Path of the KML file")
  String kmlFilePath;

  @CommandLine.Option(names = {"-d", "--dslFilePath"}, paramLabel = "<dslFilePath>", defaultValue = "null", description = "File Path of the DSL script")
  String dslFilePath;

  @CommandLine.Option(names = {"-o", "--outputFilePath"}, paramLabel = "<outputFilePath>", defaultValue = "./flightplan.ms", description = "output file path")
  String outputFilePath = "./flightplan.ms";

  @CommandLine.Option(names = {"-a", "--altitude"}, paramLabel = "<altitude>", defaultValue = "15", description = "altitude of the waypoints specified")
  String altitude = "15";

  @CommandLine.Option(names = {"-p", "--platform"}, paramLabel = "<platform>", defaultValue = "python", description = "compiled code platform")
  String platform = "python";

  @CommandLine.Option(names = {"-id", "--drones"}, paramLabel = "<dronesID>", defaultValue = "ant", description = "all the drones name")
  String dronesID = "ant";
  List<String> droneList = List.of(dronesID.split("&"));
  int dronesSize = droneList.size();

  @Override
  public void run() {

    // preprocess
    var droneWaypointsDict = createDroneWaypointsDict();

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

    for (var droneID : droneList) {
      var waypointsMap = droneWaypointsDict.get(droneID);
      // get the concrete Flight plan structure
      ImmutableMap<String, Task> taskMap = ImmutableMap.from(node.child(BotPsiElementTypes.TASK).childrenOfType(BotPsiElementTypes.TASK_DECL).map(task -> Parse.createTask(task, waypointsMap)));
      var startTaskID = Parse.createMission(node.child(BotPsiElementTypes.MISSION).child(BotPsiElementTypes.MISSION_CONTENT), taskMap);
      var ast = new MissionPlan(startTaskID, taskMap);

      // code generate
      var platformPath = String.format("./%s", platform);
      try {
        ast.codeGenPython(platformPath);
      } catch (IOException e) {
        e.printStackTrace();
      }

      // build file generate
      try {
        ProcessBuilder builder = new ProcessBuilder();
        var cmd = String.format("cd %s && pipreqs . --force", platform);
        builder.command("bash", "-c", cmd);
        builder.start().waitFor(); // Wait for the command to complete
      } catch (IOException | InterruptedException e) {
        e.printStackTrace();
      }

      // zip
      try {
        FileOutputStream fos = new FileOutputStream(outputFilePath);
        ZipOutputStream zos = new ZipOutputStream(fos);

        // add a directory's files to the zip
        addToZipFile(platformPath + "/task_defs", "./task_defs", zos);
        addToZipFile(platformPath + "/mission", "./mission", zos);
        addToZipFile(platformPath + "/transition_defs", "./transition_defs", zos);

        // add build file to the zip
        Path buildFile = Paths.get(String.format("./%s/requirements.txt", platform));
        zos.putNextEntry(new ZipEntry("requirements.txt"));
        Files.copy(buildFile, zos);
        zos.closeEntry();


        zos.close();
        fos.close();
      } catch (IOException e) {
        e.printStackTrace();
      }
    }
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

  private Map<String, Map<String, List<Compiler.Pt>>> createDroneWaypointsDict() {
    Map<String, Map<String, List<Compiler.Pt>>> droneWaypointsDict = new HashMap<>();

    // parse the set of coordinates into subset
    String currAltitude = altitude;

    for (int droneIdx = 0; droneIdx < dronesSize; droneIdx++) {
      // increment 3 meters for each drone's flight for ATC
      currAltitude = String.valueOf(Double.parseDouble(currAltitude) + 3);

      updateDroneWaypointsDict(droneIdx, currAltitude, droneWaypointsDict);
    }

    return droneWaypointsDict;
  }

  private void updateDroneWaypointsDict(int droneIdx, String currAltitude, Map<String, Map<String, List<Compiler.Pt>>> droneWaypointsDict) {
    try {
      DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
      DocumentBuilder builder = factory.newDocumentBuilder();
      Scanner scanner = new Scanner(System.in);

      // Replace this with your KML file path or an InputStream
      Document document = builder.parse(kmlFilePath);
      NodeList placemarks = document.getElementsByTagName("Placemark");


      // build the map
      for (int i = 0; i < placemarks.getLength(); i++) {
        // parseKML
        Node placemark = placemarks.item(i);
        if (placemark.getNodeType() == Node.ELEMENT_NODE) {
          Element placemarkElement = (Element) placemark;
          String waypointName = placemarkElement.getElementsByTagName("name").item(0).getTextContent();
          if (!Objects.equals(waypointName, "takeoff")) { // partition every area except takeoff

            // get waypoints
            List<String> waypoints = List.of(placemarkElement.getElementsByTagName("coordinates").item(0).getTextContent().trim().split("\\s+"));

            // get the subset size
            int subsetSize = waypoints.size() / dronesSize;

            // sub waypoints for each drone
            int startIdx = droneIdx * subsetSize;
            int endIdx = (droneIdx == droneList.size() - 1) ? waypoints.size() : startIdx + subsetSize;
            List<String> subWaypoints = waypoints.subList(startIdx, endIdx);


            // get the waypointMap
            String droneID = droneList.get(droneIdx);
            Map<String, List<Compiler.Pt>> waypointsMap = null;
            if (i == 0) {
              waypointsMap = new HashMap<>();
              droneWaypointsDict.put(droneID, waypointsMap);
            } else {
              waypointsMap = droneWaypointsDict.get(droneID);
            }

            // update the waypointMap
            updateWaypointsMap(waypointName, subWaypoints, waypointsMap, currAltitude);
          }
        }
      }

      scanner.close();
    } catch (Exception e) {
      e.printStackTrace();
    }
  }


  private static void updateWaypointsMap(String waypointName, List<String> waypoints, Map<String, List<Compiler.Pt>> waypointsMap, String altitude) {
    List<Compiler.Pt> coords = new ArrayList<>();
    for (String coordinate : waypoints) {
      String[] coordinate_ele = coordinate.split(",");
      if (coordinate_ele.length >= 2) { // Making sure there are at least longitude and latitude
        String longitude = coordinate_ele[0];
        String latitude = coordinate_ele[1];
        var pt = new Pt(longitude, latitude, altitude);
        coords.add(pt);
      }
      waypointsMap.put(waypointName, coords);
    }
  }

  @NotNull
  private static DslParserImpl parser() {
    return new DslParserImpl(new StreamReporter(System.out));
  }

  public static void main(String[] args) {
    int exitCode = new CommandLine(new Compiler()).execute(args);
    System.exit(exitCode);
  }
}
