<!--
SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab

SPDX-License-Identifier: GPL-2.0-only
-->

SteelEagle: Edge-Enabled Drone Autonomy
===========

Introduction
------------
SteelEagle is a software suite that transforms commercial-off-the-shelf (COTS) drones into fully-autonomous, beyond-visual-line-of-sight (BVLOS) UAVs. This allows users to develop complex autonomous UAV applications without needing to purchase or configure expensive aircraft hardware. SteelEagle drones are easy to deploy and importantly, are drone agnostic. This means that SteelEagle can be adapted to work with any drone control API, as long as it supports control over WiFi. Of particular interest to us are extremely lightweight drones because of the simplified regulatory approval process.

Publications
------------

[Democratizing Drone Autonomy Via Edge Computing](https://ieeexplore.ieee.org/document/10419264) - ACM SEC 2023

[The OODA Loop of Cloudlet-Based Autonomous Drones](https://ieeexplore.ieee.org/document/10818112) - ACM SEC 2024

Documentation
--------------

[**Quickstart**](https://cmusatyalab.github.io/steeleagle/getting_started/overview/)

[**Documentation**](https://cmusatyalab.github.io/steeleagle/)

License
-----
Unless otherwise stated in the table below, all source code and documentation are under the [GNU Public License, Version 2.0](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html).
A copy of this license is reproduced in the [LICENSE](LICENSE) file.

Portions from the following third party sources have
been modified and are included in this repository.
These portions are noted in the source files and are
copyright their respective authors with
the licenses listed.

Project | Modified | License
---|---|---|
[cmusatyalab/openscout](https://github.com/cmusatyalab/openscout) | Yes | Apache 2.0
[bytedeco/javacv](https://github.com/bytedeco/javacv) | Yes | Apache 2.0
[xianglic/droneDSL](https://github.com/xianglic/droneDSL) | Yes | GPL 3.0

Design
------
SteelEagle is separated into three distinct parts: the local commander client, the cloudlet server, and the onboard software. The commander client is intended to run on a personal computer close to the RPIC (Remote Pilot-in-Command) with an internet connection. It gives an interface to receive telemetry and upload a mission script to the drone. It also provides tools to assume manual control of the drone while it is in-flight. The cloudlet server is the bridge between the onboard drone software and the commander client. It relays messages between the two and also publicly hosts flight scripts. Additionally, the server runs compute engines for the drone which will be executed on the offloaded sensor data/video stream. Finally, the onboard software consists of an app that runs on the drone-mounted Android or router device. This app relays telemetry and offloads sensor data/video frames to the cloudlet server. In the Android case, it is also responsible for running the mission script and directly sending control commands to the drone. In the router case, the cloudlet runs the mission script and sends control commands over the network to the drone.

Architecture
------
![drawing](https://github.com/cmusatyalab/steeleagle/blob/main/docs/modules/images/system-arch.png)

Workflow
--------
1. A planner utilizes Google MyMaps to define the mission in a graphical UI by creating tasks. A task is created by drawing a polygon/marker, naming it, and defining the actions associated with that task by adding these to the description textbox.

2. Once defined, the planner exports the mission as a KML file.

3. The planner generates a mission script (`.ms` file) from the KML file using the Hermes compiler.

4. The pilot powers on the drone, starts the onboard software, connects to the drone through the commander, and sends the `.ms` file.

5. The drone executes its mission.



