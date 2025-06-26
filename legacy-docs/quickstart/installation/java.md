---
layout: default
title: Java Guide
parent: Installation
grand_parent: Quickstart
nav_order: 2
has_children: false
permalink: docs/quickstart/install/java
---
## Java Installation Guide
This section will describe how to configure the [Galaxy Watch 4](https://www.samsung.com/us/watches/galaxy-watch4/buy/) to work with SteelEagle. Ensure that you have purchased the necessary materials outlined in the [requirements section]({{ site.baseurl }}{% link quickstart/requirements.md %}).

{: .warning }

The Java version of SteelEagle only supports HITL simulation for the Parrot Anafi and does not support pure simulation. If you do not have access to a physical drone, see the [Python version of this guide]({{ site.baseurl }}{% link quickstart/installation/python.md %})

### Hardware Preparation
Set up LTE connectivity on your smartwatch. This process varies by device. You can follow instructions for Galaxy series watches [here](https://www.samsung.com/us/support/answer/ANS00082122/). Unlike the Onion, a static IP SIM is not needed on the watch. Ensure that your watch has both WiFi and LTE working properly before proceeding.

Turn off Bluetooth on your watch and on your smartphone to prevent the devices from accidentally pairing. This is necessary so that the watch does not try to establish cellular sockets over Bluetooth instead of its native modem. Turn on Do Not Disturb and turn off Automatic Fitness Tracking. These settings will prevent the App from being interrupted in flight by notifications. Then, [enable Developer Mode](https://developer.samsung.com/galaxy-watch-tizen/testing-your-app-on-galaxy-watch.html), ADB Debugging, and Debug over WiFi.

### Software Configuration
Install [Android Studio](https://developer.android.com/studio?gclid=CjwKCAiAx_GqBhBQEiwAlDNAZgxAgUEAdp3K1FGSELVC2xe6ZD2QCoR4NK4JY23yfFgdaRNWOxjktxoCkeUQAvD_BwE&gclsrc=aw.ds) and [Android SDK Tools](https://developer.android.com/tools/releases/platform-tools) on your computer. Take note of the IP address displayed under the Debug over WiFi setting on your watch. Then, connect your computer and the watch to a shared WiFi network. You should now be able to connect over ADB to the watch by running `adb connect <IP_GOES_HERE>`.

Once connected, open Android Studio and open the project contained in `steeleagle/onboard/watch/`. Set the build variant to `wearosDebug` and ensure that the Galaxy Watch is connected in the top right corner. Then, modify line 24 of the `gradle.properties` file to reflect the IP address of your backend server. You should now be able to install the app on the watch by pressing the Run button. However, as of now, the app will crash since no backend is active. This is expected behaviour. Setup of the watch is now complete and you can proceed to setting up the backend.
