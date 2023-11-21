---
layout: default
title: Installation
parent: User Guide
nav_order: 2
permalink: docs/user-guide/install
---
# Installation
Clone the SteelEagle [repository](https://github.com/cmusatyalab/steel-eagle/tree/main) onto your computer and the server which will eventually run the backend. Then, on your smartphone, install Parrot FreeFlight 6 which is available on both the [Apple App Store](https://apps.apple.com/us/app/freeflight-6/id1386165299) and [Google Play Store](https://play.google.com/store/apps/details?id=com.parrot.freeflight6&hl=en_US&gl=US&pli=1). Next, decide on a control environment: Python (Onion) or Java (smartwatch). There are advantages and disadvantages to both methods. Once you select the environment you want, follow the associated instructions below.

|  Category | Python (Onion) | Java (smartwatch) |
|:----------|:---------------|:------------------|
| Framerate | 30 FPS         | 0.7 FPS           |
| Latency   | 900ms latency  | 1200ms latency    |
| Sealed    | No             | Yes               |
| Compute   | None           | Minimal           |
| Price     | ~$110          | ~$140             |
| Battery   | ~40 min        | ~1 hour           |
| Weight    | 55g            | 39g               |
| Install   | Moderate       | Easy              |

## Python Environment
This section will describe how to configure the [Onion Omega 2 LTE](https://onion.io/store/omega2-lte-na/) to work with SteelEagle. Ensure that you have purchased the necessary materials outlined in the [requirements section]({{ site.baseurl }}{% link user-guide/requirements.md %}).

### Hardware Preparation
Insert a working compatible SIM card into your Onion Omega 2 LTE and attach the two LTE antennas to the ports labelled 4G and 4G DIV. Then, follow the steps outlined on Onion's [website](https://onion.io/omega2-lte-guide/) to complete setup. Ensure that your Onion has both WiFi and LTE working properly before proceeding.

Optionally, you may wish to use the provided SteelEagle [STL files](https://github.com/cmusatyalab/steel-eagle/tree/main/stl/) to print our custom harness for the Onion. Follow these [instructions]({{ site.baseurl }}{% link stl.md %}) for more details.

### Software Configuration
Navigate to the root directory of the SteelEagle [repository](https://github.com/cmusatyalab/steel-eagle/tree/main) on your computer. Once there, in your terminal, run `cd onboard/onion/device`. You should see one file in this directory, `onion_steup.sh`. Move this to the Onion by first connecting to the device's WiFi hotspot, then running `scp onion_setup.sh root@omega-XXXX.local:~/` where `XXXX` corresponds to the ID of your Onion (you can find this by looking at its hotspot name). The default password is `onioneer`.

Once you have copied the setup script to the Onion, run `ssh root@omega-XXXX.local` on your computer to login. Install Wireguard on the device by running `opkg --force-depends install wireguard`. Then, run `./onion_setup.sh`. Run `ls -ltrh`. You should see four new Wireguard configuration files, named `Alpha.conf`, `Bravo.conf`, `Charlie.conf`, and `Delta.conf`. These files are used to open Wireguard tunnels to talk to the Onion and the drone when in flight. It is *highly recommended* that you purchase a static IP SIM card to use with the Onion. If you do not do this, you will have to modify the configuration file on the server every time the Onion is power cycled or disconnects.

On your computer, run `scp root@omega-XXXX.local:~/X.conf .` where `X.conf` can refer to any one of the four configuration files. Then, move this file to the server under `/etc/wireguard`. Keep in mind that this directory requires root to access. Setup of the Onion is now complete and you can proceed to setting up the backend.

## Java Environment
This section will describe how to configure the [Galaxy Watch 4](https://www.samsung.com/us/watches/galaxy-watch4/buy/) to work with SteelEagle. Ensure that you have purchased the necessary materials outlined in the [requirements section]({{ site.baseurl }}{% link user-guide/requirements.md %}).

### Hardware Preparation
Set up LTE connectivity on your smartwatch. This process varies by device. You can follow instructions for Galaxy series watches [here](https://www.samsung.com/us/support/answer/ANS00082122/). Unlike the Onion, a static IP SIM is not needed on the watch. Ensure that your watch has both WiFi and LTE working properly before proceeding.

Turn off Bluetooth on your watch and on your smartphone to prevent the devices from accidentally pairing. This is necessary so that the watch does not try to establish cellular sockets over Bluetooth instead of its native modem. Turn on Do Not Disturb and turn off Automatic Fitness Tracking. These settings will prevent the App from being interrupted in flight by notifications. Then, [enable Developer Mode](https://developer.samsung.com/galaxy-watch-tizen/testing-your-app-on-galaxy-watch.html) and enable ADB Debugging and Debug over WiFi. 

### Software Configuration
Install [Android Studio](https://developer.android.com/studio?gclid=CjwKCAiAx_GqBhBQEiwAlDNAZgxAgUEAdp3K1FGSELVC2xe6ZD2QCoR4NK4JY23yfFgdaRNWOxjktxoCkeUQAvD_BwE&gclsrc=aw.ds) and [Android SDK Tools](https://developer.android.com/tools/releases/platform-tools). Take note of the IP address displayed under the Debug over WiFi setting. Then, connect your computer and the watch to a shared WiFi network. You should now be able to connect over ADB to the watch by running `adb connect <IP_GOES_HERE>`.

Once connected, open Android Studio and open the project contained in `steel-eagle/onboard/watch/`. Set the build variant to `wearosDebug` and ensure that the Galaxy Watch is connected in the top right corner. Setup of the watch is not complete and you can proceed to setting up the backend.

## Backend Setup
On the backend server, open the `steel-eagle/cnc/server` directory. 


 

