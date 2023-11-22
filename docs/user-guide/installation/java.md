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

### Hardware Preparation
Set up LTE connectivity on your smartwatch. This process varies by device. You can follow instructions for Galaxy series watches [here](https://www.samsung.com/us/support/answer/ANS00082122/). Unlike the Onion, a static IP SIM is not needed on the watch. Ensure that your watch has both WiFi and LTE working properly before proceeding.

Turn off Bluetooth on your watch and on your smartphone to prevent the devices from accidentally pairing. This is necessary so that the watch does not try to establish cellular sockets over Bluetooth instead of its native modem. Turn on Do Not Disturb and turn off Automatic Fitness Tracking. These settings will prevent the App from being interrupted in flight by notifications. Then, [enable Developer Mode](https://developer.samsung.com/galaxy-watch-tizen/testing-your-app-on-galaxy-watch.html) and enable ADB Debugging and Debug over WiFi. 

### Software Configuration
Install [Android Studio](https://developer.android.com/studio?gclid=CjwKCAiAx_GqBhBQEiwAlDNAZgxAgUEAdp3K1FGSELVC2xe6ZD2QCoR4NK4JY23yfFgdaRNWOxjktxoCkeUQAvD_BwE&gclsrc=aw.ds) and [Android SDK Tools](https://developer.android.com/tools/releases/platform-tools). Take note of the IP address displayed under the Debug over WiFi setting. Then, connect your computer and the watch to a shared WiFi network. You should now be able to connect over ADB to the watch by running `adb connect <IP_GOES_HERE>`.

Once connected, open Android Studio and open the project contained in `steel-eagle/onboard/watch/`. Set the build variant to `wearosDebug` and ensure that the Galaxy Watch is connected in the top right corner. Setup of the watch is not complete and you can proceed to setting up the backend.
