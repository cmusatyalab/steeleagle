---
sidebar_position: 2
---

# Referencing KML Objects

For many missions, users will want to correlate real world geolocations with vehicle actions.
SteelEagle DSL supports this through KML file referencing. [KML](https://developers.google.com/kml/documentation/kml_tut) (Keyhole Markup Language) files
are files used to describe geographic data. They are generally used to draw visual features on top of a
map. Users can create KML files marked up with Polylines or Polygons and inject these shapes into DSL 
datatypes, like the [`Waypoints`](/sdk/python/steeleagle_sdk/api/datatypes/waypoint#class-waypoint)
object.

## Creating a KML File

The most straightforward way to create a KML file is to use [Google MyMaps](https://www.google.com/maps/d/). MyMaps
is a free service provided by Google that allows users to create and save map drawings as KML. It is also
configured so that all saved maps are saved to Google Drive. Below is a look at the MyMaps interface:

<div style={{textAlign: 'center'}}>
![Interface Example](/img/mymaps/mymaps.png)
</div>

The two types of shapes that SteelEagle supports are Polylines and Polygons. Polylines are a line
of waypoints where the last waypoint is distinct from the first (hence it is not a closed shape).
Polygons are a line of waypoints where the last waypoint is the first (hence it is a closed shape).
To create a Polyline/Polygon:

1. Select the drawing tool from the toolbar. This can be found in the upper center of the interface under the search bar.

<div style={{textAlign: 'center'}}>
![Drawing Tools](/img/mymaps/toolbar.png)
</div>

2. Create a shape by repeatedly clicking in different locations; to create a Polyline, click the last location twice,
to create a Polygon, click the first location after clicking at least two other locations. This should bring up the
shape menu shown below. Enter whatever name you want for the shape but keep in mind that _this is the name that this
shape will have in the DSL_. Once you have chosen a name, click "Save". You may add as many shapes as you like, but
ensure they are all on the same layer.

<div style={{textAlign: 'center'}}>
![Drawing](/img/mymaps/drawingtools.png)
</div>

3. Once all shapes are created, save the layer containing the shaped by clicking on the hamburger icon in the navigation
area, then select "Export Data" &rarr; "KML/KMZ".

<div style={{textAlign: 'center'}}>
![Nav](/img/mymaps/navbar.png)
</div>

4. Finally, save the map as a KML file. This file is now ready to be used with the SteelEagle DSL!

<div style={{textAlign: 'center'}}>
![Saving](/img/mymaps/saving.png)
</div>

## DSL Integration

Now that the KML file is ready, integrating it with a DSL file is easy. For both Polyline and Polygon objects, the
SteelEagle DSL datatype analog is the [`Waypoints`](/sdk/python/steeleagle_sdk/api/datatypes/waypoint#class-waypoint).
Initialize a waypoint in the data section like so:

```dsl
Data:
    Waypoints waypoint(alt = ALTITUDE, area = SHAPE_NAME, algo = SLICE_ALGORITHM)
    # Example using the earlier shape, Polygon 1:
    Waypoints waypoint(alt = 5.0, area = 'Polygon 1', algo = 'corridor')
```

Waypointss provide two settings in addition to the KML reference parameter `area`. These are:
- `alt`: the altitude above mean sea level (MSL) at which the vehicle should visit the waypoints (_UAV only_).
- `algo`: the algorithm for how to slice the waypoints (see [waypoint slicing](#waypoint-slicing)).

If multiple shapes are defined in the KML file, add them as separate waypoint objects:

```dsl
Data:
    Waypoints waypoint_1(alt = 5.0, area = 'Polygon 1', algo = 'corridor')
    Waypoints waypoint_2(alt = 7.0, area = 'Polygon 2', algo = 'corridor')
    Waypoints waypoint_3(alt = 3.0, area = 'Polyline 1', algo = 'edge')
```

These can then be used as parameters to actions:

```dsl
Actions:
    Patrol patrol(patrol_path = waypoint_1)
```

### Waypoints Slicing

Users may want vehicles to traverse Polylines/Polygons in several different ways. To support this,
SteelEagle DSL has three native waypoint slicing algorithms built in: edge, survey, and corridor. These
algorithms divide the waypoints into subpoints which either attempt to cover the input area or transit
along its edges.
