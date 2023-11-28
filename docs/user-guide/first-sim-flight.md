---
layout: default
title: First Simulated Flight
parent: User Guide
nav_order: 5
has_children: false
permalink: docs/user-guide/first-sim-flight
---
# First Simulated Flight
All systems are ready to go and it's now time to start your first mission! Connect the watch or Onion Omega to your drone's WiFi hotspot. 

{: .warning }

The Onion Omega 2 LTE's WiFi can only connect to 2.4GHz networks. Here is a [tutorial](https://www.youtube.com/watch?v=B6kM8BnshsY) on how to change your drone's WiFi hotspot to 2.4GHz.

If using the watch, start the watch app. It should show a drone symbol when it has connected to the backend. 

If using the Onion, on your backend server, run `cd /path/to/steel-eagle/onboard/onion/remote`. Ensure that the Wireguard tunnel is open to the drone by running `sudo wg show`. You should see the tunnel active. You should also be able to ping the drone by running `ping 192.168.42.1`. If both of these actions are successful, run `python3 supervisor.py -s localhost`. You should see Parrot Olympe output messages conaining telemetry from the drone.

Once the Onion or watch are connected, navigate to the root directory of the SteelEagle repository on your computer and run `cd cnc/python_client`. Install requirements with `pip3 install -r requirements.txt` then start the commander by running `python3 commander_client.py -s <IP_OF_BACKEND_SERVER>`. The commander interface should now be visible.

In the top right, under available drones, you should see your drone name listed. Click on it and click connect. You should now be able to send a takeoff command by holding down T and moving using the WASD keys. A stream from the drone should be visible in the right panel. You should also see telemetry printed on the commander.

{: .note }

The Sphinx environment video stream through the watch is low quality and subject to significant artifacting. In real environments, the camera stream does not experience the same issues.

Congratulations! You have now flown your first flight with SteelEagle.


