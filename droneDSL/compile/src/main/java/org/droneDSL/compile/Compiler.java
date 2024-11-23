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

@CommandLine.Command(name = "DroneDSL Compiler", version = "DroneDSL Compiler 1.5", mixinStandardHelpOptions = true)
public class Compiler implements Runnable {
  public record Pt(@NotNull String longitude, @NotNull String latitude, @NotNull String altitude) {
  }

  @CommandLine.Option(names = {"-k", "--KMLFilePath"}, paramLabel = "<KMLFilePath>", defaultValue = "null", description = "File Path of the KML file")
  String KMLFilePath;

  @CommandLine.Option(names = {"-s", "--DSLScriptPath"}, paramLabel = "<DSLScriptPath>", defaultValue = "null", description = "File Path of the DSL script")
  String DSLScriptPath;

  @CommandLine.Option(names = {"-o", "--OutputFilePath"}, paramLabel = "<OutputFilePath>", defaultValue = "./flightplan_", description = "output file path")
  String OutputFilePath = "./flightplan_";

  @CommandLine.Option(names = {"-a", "--Altitude"}, paramLabel = "<Altitude>", defaultValue = "15", description = "altitude of the waypoints specified")
  String Altitude = "12";

  @CommandLine.Option(names = {"-p", "--Platform"}, paramLabel = "<Platform>", defaultValue = "python/project", description = "compiled code platform")
  String Platform = "python/project";

  @CommandLine.Option(names = {"-d", "--Drones"}, paramLabel = "<Drones>", defaultValue = "ant", description = "all the drones name")
  String Drones = "ant";


  @Override
  public void run() {
    // drone info
    List<String> droneList = List.of(Drones.split("&"));

    // preprocess
    Map<String, Map<String, List<Compiler.Pt>>> droneWaypointsDict;
    try{
      droneWaypointsDict = createDroneWaypointsDict(droneList);
    } catch (Exception e){
      System.err.println("Error parsing the kml file: " + e.getMessage());
      return;
    }


    // get the DSL script file
    String fileContent;
    try {
      fileContent = Files.readString(Paths.get(DSLScriptPath));
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
      var platformPath = Platform;
      try {
        ast.codeGenPython(platformPath);
      } catch (IOException e) {
        e.printStackTrace();
      }

      // build file generate
      try {
        ProcessBuilder builder = new ProcessBuilder();
        var cmd = String.format("cd %s && pipreqs . --force", Platform);
        builder.command("bash", "-c", cmd);
        builder.start().waitFor(); // Wait for the command to complete
      } catch (IOException | InterruptedException e) {
        e.printStackTrace();
      }

      // zip
      try {
        FileOutputStream fos = new FileOutputStream(String.format(OutputFilePath+droneID+".ms"));
        ZipOutputStream zos = new ZipOutputStream(fos);
        // add to the zip file
        addToZipFile(platformPath, "", zos);
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

    // Check if the directory exists and contains files
    if (files != null) {
      for (File file : files) {
        // If it's a directory, recursively process the files inside this directory
        if (file.isDirectory()) {
          // Create the corresponding directory inside the ZIP file
          addToZipFile(file.getAbsolutePath(), insideZipDir + "/" + file.getName(), zos);
        } else {
          // If it's a file, add it to the ZIP file
          zos.putNextEntry(new ZipEntry(insideZipDir + "/" + file.getName()));
          Files.copy(file.toPath(), zos);
          zos.closeEntry();
        }
      }
    }
  }

  private Map<String, Map<String, List<Compiler.Pt>>> createDroneWaypointsDict(List<String> droneList) {
    Map<String, Map<String, List<Compiler.Pt>>> droneWaypointsDict = new HashMap<>();
    String currAltitude = Altitude;
    updateDroneWaypointsDict(currAltitude, droneWaypointsDict, droneList);
    return droneWaypointsDict;
  }

  private void updateDroneWaypointsDict(String currAltitude, Map<String, Map<String, List<Compiler.Pt>>> droneWaypointsDict, List<String> droneList) {
    try {
      DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
      DocumentBuilder builder = factory.newDocumentBuilder();
      Scanner scanner = new Scanner(System.in);

      // Replace this with your KML file path or an InputStream
      Document document = builder.parse(KMLFilePath);
      NodeList placemarks = document.getElementsByTagName("Placemark");


      // build the map
      boolean firstTime = true;
      for (int i = 0; i < placemarks.getLength(); i++) {
        // parseKML
        Node placemark = placemarks.item(i);
        if (placemark.getNodeType() == Node.ELEMENT_NODE) {
          Element placemarkElement = (Element) placemark;
          String areaName = placemarkElement.getElementsByTagName("name").item(0).getTextContent();
          if (!Objects.equals(areaName, "takeoff")) { // partition every area except takeoff
            // get waypoints
            List<String> areaWaypoints = List.of(placemarkElement.getElementsByTagName("coordinates").item(0).getTextContent().trim().split("\\s+"));

            // parse the waypoints for drones
            parseWaypointsForDrones(droneList, areaName, currAltitude, firstTime, areaWaypoints, droneWaypointsDict);
            firstTime = false;
          }
        }
      }

      scanner.close();
    } catch (Exception e) {
      e.printStackTrace();
    }
  }

  private void parseWaypointsForDrones(List<String> droneList, String areaName, String currAltitude, boolean firstTime, List<String> areaWaypoints, Map<String, Map<String, List<Compiler.Pt>>> droneWaypointsDict){
    int startIdx = 0;
    int endIdx = 0;
    int edgesPerDrone = (areaWaypoints.size() -1) / droneList.size();
    // sub waypoints for each drone
    for (int droneIdx = 0; droneIdx < droneList.size(); droneIdx++) {
      // increment 3 meters for each drone's flight for ATC
      currAltitude = String.valueOf(Double.parseDouble(currAltitude) + 3);
      startIdx = (droneIdx == 0) ? 0: endIdx -1;
      endIdx = (droneIdx == droneList.size() - 1) ? areaWaypoints.size() : startIdx + edgesPerDrone + 1;

      List<String> subWaypoints = areaWaypoints.subList(startIdx, endIdx);
      // get the waypointMap
      String droneID = droneList.get(droneIdx);
      Map<String, List<Compiler.Pt>> waypointsMap;

      if (firstTime) { // first time and create the map
        waypointsMap = new HashMap<>();
        droneWaypointsDict.put(droneID, waypointsMap);
      } else {
        waypointsMap = droneWaypointsDict.get(droneID);
      }

      // update the waypointMap
      updateWaypointsMap(areaName, subWaypoints, waypointsMap, currAltitude);
    }
  }
  private static void updateWaypointsMap(String areaName, List<String> areaWaypoints, Map<String, List<Compiler.Pt>> waypointsMap, String altitude) {
    List<Compiler.Pt> coords = new ArrayList<>();
    for (String waypoint : areaWaypoints) {
      String[] coordinate_ele = waypoint.split(",");
      if (coordinate_ele.length >= 2) { // Making sure there are at least longitude and latitude
        String longitude = coordinate_ele[0];
        String latitude = coordinate_ele[1];
        var pt = new Pt(longitude, latitude, altitude);
        coords.add(pt);
      }
      waypointsMap.put(areaName, coords);
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
