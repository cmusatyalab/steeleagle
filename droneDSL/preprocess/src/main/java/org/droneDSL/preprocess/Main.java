package org.droneDSL.preprocess;

import com.google.gson.Gson;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.FileWriter;
import java.io.Serializable;
import java.util.*;


public class Main {
  public record Pt(
      String longitude,
      String latitude,
      String altitude
  ) implements Serializable {
  }

  public static void main(String[] args) {
    try {
      DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
      DocumentBuilder builder = factory.newDocumentBuilder();
      Scanner scanner = new Scanner(System.in);

      // Replace this with your KML file path or an InputStream
      Document document = builder.parse(args[0]);
      NodeList placemarks = document.getElementsByTagName("Placemark");
      Map<String, List<Pt>> lineCoordinates = new HashMap<>();



      for (int i = 0; i < placemarks.getLength(); i++) {

        Node placemark = placemarks.item(i);
        if (placemark.getNodeType() == Node.ELEMENT_NODE) {

          Element placemarkElement = (Element) placemark;
          String name = placemarkElement.getElementsByTagName("name").item(0).getTextContent();
          // Prompt the user to enter a number
          System.out.print("Please enter the altitude for " + name + " : \n");
          // Read the number entered by the user
          Double var = scanner.nextDouble();
          String altitude = String.valueOf(var);
          System.out.print("Entered " + altitude + " : \n");

          NodeList coordinateList = placemarkElement.getElementsByTagName("coordinates");

          String[] coordinates = coordinateList.item(0).getTextContent().trim().split("\\s+");
          List<Pt> coords = new ArrayList<>();
          for (String coordinate : coordinates) {
            String[] coordinate_ele = coordinate.split(",");
            if (coordinate_ele.length >= 2) { // Making sure there are at least longitude and latitude
              String longitude = coordinate_ele[0];
              String latitude = coordinate_ele[1];


              var pt = new Pt(longitude, latitude, altitude);

              coords.add(pt);

            }
            lineCoordinates.put(name, coords);
          }

        }
      }

      // Example of retrieving data
      for (var entry : lineCoordinates.entrySet()) {
        System.out.println("Name: " + entry.getKey() + " - Coordinates: " + entry.getValue());
      }

      // Convert map to JSON
      Gson gson = new Gson();
      String json = gson.toJson(lineCoordinates);

      // Write JSON to file
      try (FileWriter writer = new FileWriter("../shared_dir/coordinates.json")) {
        writer.write(json);
      }

      scanner.close();
    } catch (Exception e) {
      e.printStackTrace();
    }
  }
}
