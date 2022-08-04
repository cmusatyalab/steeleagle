# Hermes

## Description
Hermes is used to compile a fligh plan designed in MyMaps and exported as a .kml/.kmz file, to drone flight commands. [Github pages](https://cmusatyalab.github.io/steel-eagle/) contains the current list of supported tasks. It uses jinja templating to generate a platform-agnostic mission script (or MS) in java. The MS contains drone and cloudlet facing commands at a high level, which correspond to the tasks defined in the .kml file. A drone platform is also specified in the MS and instructs the app onboard the drone which low-level drone implementation to use.

## Prerequisites

### System Binary Requirements

In order to compile the MS into a Java class file and subsequently an Android-ready .dex file, Hermes requires binaries for javac, d8, and a .jar containing a version of the Android SDK to compile against. The simplest way to obtain these is to install a version of [Android Studio](https://developer.android.com/studio) and then have it install a version of the Android SDK. You can then point Hermes to the paths to the paths to those files that Android Studio has installed using the below options. If you are building the [onboard Android app](https://github.com/cmusatyalab/steel-eagle/tree/main/onboard/DroneBrain) that is also part of this repository, then you likely have already done this.

### Python Requirements

Hermes uses the jinja2 and jsonschema libraries. Task documentation (from ```task_stubs.py```) is generated using the json-schema-for-humans library. They can be installed with pip:
```sh
pip install Jinja2 jsonschema json-schema-for-humans
```

## Usage
```sh
usage: hermes [-h] [-p {anafi,dji}] [-o OUTPUT] [-v] [-t TEMPLATE]
              [-w WORLD_TEMPLATE] [-wo WORLD_OUTPUT] [-da DASHBOARD_ADDRESS]
              [-dp DASHBOARD_PORT] [-s] [-sa] [-c] [-jc JAVAC_PATH]
              [-d8 D8_PATH] [-a ANDROID_JAR]
              input

Convert kml/kmz file to drone-specific instructions.

positional arguments:
  input                 kml/kmz file to convert

optional arguments:
  -h, --help            show this help message and exit
  -p {anafi,dji}, --platform {anafi,dji}
                        Drone platform to convert to [default: Anafi]
  -o OUTPUT, --output OUTPUT
                        Filename for generated drone instructions [default:
                        ./src/edu/cmu/cs/dronebrain/MS.java]
  -v, --verbose         Write output to console as well [default: False]
  -t TEMPLATE, --template TEMPLATE
                        Specify a jinja2 template [default: base.java.jinja2]
  -w WORLD_TEMPLATE, --world_template WORLD_TEMPLATE
                        Specify a jinja2 template [default:
                        empty.world.jinja2]
  -wo WORLD_OUTPUT, --world_output WORLD_OUTPUT
                        Specify a world output file [default: sim.world]
  -da DASHBOARD_ADDRESS, --dashboard_address DASHBOARD_ADDRESS
                        Specify address of dashboard to send heartbeat to
                        [default: steel-eagle-
                        dashboard.pgh.cloudapp.azurelel.cs.cmu.edu]
  -dp DASHBOARD_PORT, --dashboard_port DASHBOARD_PORT
                        Specify dashboard port [default: 8080]
  -s, --sim             Connect to simulated drone at 10.202.0.1 [default:
                        Direct connection to drone at 192.168.42.1]
  -sa, --sample         Sample rate for transponder/log file
  -c, --controller      Connect to drone via SkyController at 192.168.53.1
                        [default: Direct connection to drone at 192.168.42.1]
  -jc JAVAC_PATH, --javac_path JAVAC_PATH
                        Specify a the path to javac [default: ~/android-
                        studio/jre/bin/javac]
  -d8 D8_PATH, --d8_path D8_PATH
                        Specify a the path to d8 [default:
                        ~/Android/Sdk/build-tools/30.0.3/d8]
  -a ANDROID_JAR, --android_jar ANDROID_JAR
                        Specify a the path to Android SDK jar [default:
                        ~/Android/Sdk/platforms/android-30/android.jar]
```
Hermes requires a .kml/.kmz file as input. Beyond that, most options have a default value that can be used or overriden if necessary (e.g. when building an MS for a simulated drone or for a drone to be controlled by a SkyController). **NOTE: There are 3 paths required for Hermes to properly compile the Java class and build it into a .dex file for Android. The default values most likely need to be overriden to correspond to where you have these binaries**

Once Hermes has successfully run, there should be a classes.dex file in the ```steel-eagle/hermes/src``` directory. This file will need to be served by some web server that is publicly accessible to the Android app running onboard the drone.

## New/Updated Task Specifications
In order to provide new/updated tasks, we need to do a few things:

1. task_stubs.py should be updated include the validation parameters that jsonschema will use to ensure that the task is defined properly in the description field(s) of the .kml file that is input to Hermes.
2. ```base.java.jinja2``` needs to be updated to reflect the name of the new/updated task(s) when iterating through placemarks.
3. The github pages documentation (it has its own [branch](https://github.com/cmusatyalab/steel-eagle/tree/gh-pages) in the repo) should be updated to include the syntax of the new task and its description/parameters. To update the documentation, task_stubs.py can be executed and uses the json_schema_for_humans library to generate HTML files related to the documentation which are output to the ```task_docs``` directory.
