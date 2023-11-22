---
layout: default
title: Java Guide
parent: Installation
grand_parent: User Guide
nav_order: 2
has_children: false
permalink: docs/user-guide/install/java
---
## Java Environment
This section will describe how to configure the [Galaxy Watch 4](https://www.samsung.com/us/watches/galaxy-watch4/buy/) to work with SteelEagle. Ensure that you have purchased the necessary materials outlined in the [requirements section]({{ site.baseurl }}{% link user-guide/requirements.md %}).

{: .warning }

The Java version of SteelEagle only supports HITL simulation for the Parrot Anafi and does not support pure simulation. If you do not have access to a physical drone, see the [Python version of this guide]({{ site.baseurl }}{% link user-guide/installation/python.md %}) 

### Hardware Preparation
Set up LTE connectivity on your smartwatch. This process varies by device. You can follow instructions for Galaxy series watches [here](https://www.samsung.com/us/support/answer/ANS00082122/). Unlike the Onion, a static IP SIM is not needed on the watch. Ensure that your watch has both WiFi and LTE working properly before proceeding.

Turn off Bluetooth on your watch and on your smartphone to prevent the devices from accidentally pairing. This is necessary so that the watch does not try to establish cellular sockets over Bluetooth instead of its native modem. Turn on Do Not Disturb and turn off Automatic Fitness Tracking. These settings will prevent the App from being interrupted in flight by notifications. Then, [enable Developer Mode](https://developer.samsung.com/galaxy-watch-tizen/testing-your-app-on-galaxy-watch.html), ADB Debugging, and Debug over WiFi. 

### Software Configuration
Install [Android Studio](https://developer.android.com/studio?gclid=CjwKCAiAx_GqBhBQEiwAlDNAZgxAgUEAdp3K1FGSELVC2xe6ZD2QCoR4NK4JY23yfFgdaRNWOxjktxoCkeUQAvD_BwE&gclsrc=aw.ds) and [Android SDK Tools](https://developer.android.com/tools/releases/platform-tools) on your computer. Take note of the IP address displayed under the Debug over WiFi setting on your watch. Then, connect your computer and the watch to a shared WiFi network. You should now be able to connect over ADB to the watch by running `adb connect <IP_GOES_HERE>`.

Once connected, open Android Studio and open the project contained in `steel-eagle/onboard/watch/`. Set the build variant to `wearosDebug` and ensure that the Galaxy Watch is connected in the top right corner. You should now be able to install the app on the watch by pressing the Run button. However, as of now, the app will crash since no backend is active. This is expected behaviour. Setup of the watch is now complete and you can proceed to setting up the backend.

### Backend Preparation
Ensure your server is publicly accessible over the Internet. Then, navigate to the root directory of the SteelEagle [repository](https://github.com/cmusatyalab/steel-eagle/tree/main) on your server and run `cd cnc`. Then run `docker build . -t cmusatyalab/steel-eagle:latest`. This will build a container for the SteelEagle backend.

Next, you will need to set up the OpenScout backend which is responsible for running compute engines like object detection. clone the OpenScout [repository](https://github.com/cmusatyalab/openscout) onto the server, navigate to its root directory, and run `git checkout steel-eagle` followed by `docker build . -t cmusatyalab/openscout:steel-eagle`.

Finally, navigate back to the SteelEagle root directory and run `cd cnc/server` followed by `docker-compose up -d`. This will start the backend in the background.

The full command list is as follows:
```
cd /path/to/steel-eagle/cnc
# Build the SteelEagle backend
docker build . -t cmusatyalab/steel-eagle:latest
git clone git@github.com:cmusatyalab/openscout.git
cd /path/to/openscout
# Checkout the SteelEagle branch of OpenScout
git checkout steel-eagle
# Build the OpenScout backend
docker build . -t cmusatyalab/openscout:steel-eagle
cd /path/to/steel-eagle/cnc/server
# Start the backend!
docker-compose up -d
```

### Simulator Installation
Parrot Sphinx is a simulation environment for ANAFI series drones built on top of Unreal Engine 4. SteelEagle, by design, is compatible with most simulation environments that support HITL. This tutorial will use Sphinx to simulate a basic SteelEagle mission without flying the drone.

First, create links to the Parrot repositories by running:
```
curl --fail --silent --show-error --location https://debian.parrot.com/gpg | gpg --dearmor | sudo tee /usr/share/keyrings/debian.parrot.com.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/debian.parrot.com.gpg] https://debian.parrot.com/ $(lsb_release -cs) main generic" | sudo tee /etc/apt/sources.list.d/debian.parrot.com.list
sudo apt update
``` 

Then, install Sphinx by running `sudo apt install parrot-sphinx` on your computer. You will also need to install a test environment. For example, you may run `sudo apt install parrot-ue4-empty`. The full list of test environments is available [here](https://developer.parrot.com/docs/sphinx/available_worlds.html) or by running `apt-cache search parrot-ue4`.

Plug your Parrot ANAFI into your computer using a USB C cable. Then, follow these [instructions](https://developer.parrot.com/docs/sphinx/wifi_setup.html) to set up your drone for HITL.

Next, start the firmwared service by running `sudo systemctl start firmwared.service`. Then, start Sphinx by running:
```
sphinx "/opt/parrot-sphinx/usr/share/sphinx/drones/anafi.drone"::firmware="https://firmware.parrot.com/Versions/anafi/pc/%23latest/images/anafi-pc.ext2.zip"
```

In a different terminal tab, run `parrot-ue4-empty` or an equivalent simulation environment command.

{: .note }

The Parrot Sphinx website instructs you to install the Parrot Anafi Ai firmware. This tutorial works with the Parrot Anafi so a different firmware link has been provided.

### First Flight
All systems are ready to go and it's now time to start your first mission! Connect the watch to the drone's WiFi. Then, start the app. It should show a drone symbol when it has connected to the backend. If for whatever reason this does not happen, see TODO: TROUBLESHOOTING. 

Once the logo is visible, navigate to the root directory of the SteelEagle repository and run `cd cnc/python_client`. Install requirements with `pip3 install -r requirements.txt` then start the commander by running `python3 commander_client.py -s <IP_OF_BACKEND_SERVER>`. The commander interface should now be visible.

In the top right, under available drones, you should see your drone name listed. Click on it and click connect. You should now be able to send a takeoff command by holding down T and moving using the WASD keys. A stream from the drone should be visible in the right panel.

{: .note }

The Sphinx environment video stream through the watch is low quality and subject to significant artifacting. In real environments, the camera stream does not experience the same issues.

Congratulations! You have now flown your first flight with SteelEagle. See TODO: MISSION CREATION to start building your own autonomous missions.
