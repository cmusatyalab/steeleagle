---
layout: default
title: Simulator Setup
parent: Quickstart
nav_order: 4
has_children: false
permalink: docs/quickstart/simulator
---
# Simulator Setup
Parrot Sphinx is a simulation environment for ANAFI series drones built on top of Unreal Engine 4. SteelEagle, by design, is compatible with most simulation environments that support HITL. This tutorial will use Sphinx to simulate a basic SteelEagle mission without flying the drone.

## Parrot Sphinx Installation
First, create links to the Parrot repositories by running:
```
curl --fail --silent --show-error --location https://debian.parrot.com/gpg | gpg --dearmor | sudo tee /usr/share/keyrings/debian.parrot.com.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/debian.parrot.com.gpg] https://debian.parrot.com/ $(lsb_release -cs) main generic" | sudo tee /etc/apt/sources.list.d/debian.parrot.com.list
sudo apt update
```

{: .note }

The Parrot Sphinx website instructs you to install the Parrot Anafi Ai firmware. This tutorial works with the Parrot Anafi so a different firmware link has been provided.

Then, install Sphinx by running `sudo apt install parrot-sphinx` on your computer. You will also need to install a test environment. For example, you may run `sudo apt install parrot-ue4-empty`. The full list of test environments is available [here](https://developer.parrot.com/docs/sphinx/available_worlds.html) or by running `apt-cache search parrot-ue4`.

## Hardware-in-the-Loop
While it is not necessary, it is **strongly recommended** that you run at least one Hardware-in-the-Loop (HITL) flight before graduating to real flights. Plug your Parrot ANAFI into your computer using a USB C cable. Then, follow these [instructions](https://developer.parrot.com/docs/sphinx/wifi_setup.html) to set up your drone for HITL.

Next, start the firmwared service by running `sudo systemctl start firmwared.service`. Then, start Sphinx by running:
```
sphinx "/opt/parrot-sphinx/usr/share/sphinx/drones/anafi.drone"::firmware="https://firmware.parrot.com/Versions/anafi/pc/%23latest/images/anafi-pc.ext2.zip"
```

In a different terminal tab, run `parrot-ue4-empty` or an equivalent simulation environment command. You should see an Unreal Engine environment start up with a simulated version of your drone located at the center of the screen.
