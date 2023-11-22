---
layout: default
title: Hermes
nav_order: 3
has_children: true
permalink: docs/hermes
---

# Hermes

Hermes is used to compile a flight plan designed in MyMaps and exported as a .kml/.kmz file, to drone flight commands. It uses jinja templating to generate a platform-agnostic mission script (or MS) in java. The MS contains drone and cloudlet facing commands at a high level, which correspond to the tasks defined in the .kml file. A drone platform is also specified in the MS which instructs the app onboard the drone which low-level drone implementation to use.

## Prerequisites

### Java Requirements

In order to compile the MS into a Java class file and subsequently an Android-ready .dex file, Hermes uses the [Gradle](https://gradle.org/) build system. Edit the [build.gradle](https://github.com/cmusatyalab/steel-eagle/blob/main/hermes/java/app/build.gradle) to add new dependencies for tasks.

### Python Requirements

Hermes uses the jinja2 and jsonschema libraries. Task documentation (from ```task_stubs.py```) is generated using the json-schema-for-humans library. They can be installed with pip:
```sh
pip install Jinja2 jsonschema json-schema-for-humans
```

## Usage
```bash
usage: hermes [-h] [-p {java,python}] [-o OUTPUT] [-v] [-s] input

Convert kml/kmz file to drone-specific instructions.

positional arguments:
  input                 kml/kmz file to convert

optional arguments:
  -h, --help            show this help message and exit
  -p {java,python}, --platform {java,python}
                        Drone autopilot language to convert to [default: java (Parrot GroundSDK)]
  -o OUTPUT, --output OUTPUT
                        Filename for .ms (mission script) file [default: ./flightplan.ms]
  -v, --verbose         Write output to console as well [default: False]
  -s, --sim             Connect to simulated drone instead of a real drone [default: False]

```
Hermes requires a .kml/.kmz file as input. Beyond that, most options have a default value that can be used or overriden if necessary (e.g. when building an MS for a simulated drone). 
Once Hermes has successfully run, there should be a flightplan.ms file in the ```steel-eagle/hermes/``` directory. This file can then be uploaded from a [commander]({{ site.baseurl }}{% link commander.md %}) and sent to a connected drone.

## New/Updated Task Specifications
In order to provide new/updated tasks, we need to do a few things:

1. [task_stubs.py](https://github.com/cmusatyalab/steel-eagle/blob/main/hermes/docs/task_stubs.py) should be updated include the validation parameters that jsonschema will use to ensure that the task is defined properly in the description field(s) of the .kml file that is input to Hermes. Create a new class the defines the schema and defaults (see current tasks for examples). One can think of this file as the function definition of the task. 
2. Implement the task for either [Java](https://github.com/cmusatyalab/steel-eagle/tree/main/hermes/java/app/src/main/java/edu/cmu/cs/dronebrain/tasks) or [Python](https://github.com/cmusatyalab/steel-eagle/tree/main/hermes/python/task_defs) (or both). These contain the actual code that will be run on board the drone. The arguments given in the KML file will be accessible via the kwargs variable. ***NOTE: The name of the task class must match the name specified in task_stubs.py in step 1***
