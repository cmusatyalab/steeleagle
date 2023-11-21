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

1. task_stubs.py should be updated include the validation parameters that jsonschema will use to ensure that the task is defined properly in the description field(s) of the .kml file that is input to Hermes.
2. ```base.java.jinja2``` needs to be updated to reflect the name of the new/updated task(s) when iterating through placemarks.
3. The github pages documentation (under /docs/hermes/tasks in the repo) should be updated to include the syntax of the new task and its description/parameters. To update the documentation, task_stubs.py can be executed and uses the json_schema_for_humans library to generate HTML files related to the documentation which are output to the ```task_docs``` directory.
