---
layout: default
title: Python Guide
parent: Installation
grand_parent: User Guide
nav_order: 1
has_children: false
permalink: docs/user-guide/install/python
---
## Python Installation Guide
This section will describe how to configure the [Onion Omega 2 LTE](https://onion.io/store/omega2-lte-na/) to work with SteelEagle. Ensure that you have purchased the necessary materials outlined in the [requirements section]({{ site.baseurl }}{% link user-guide/requirements.md %}).

### Hardware Preparation
Insert a working compatible SIM card into your Onion Omega 2 LTE and attach the two LTE antennas to the ports labelled 4G and 4G DIV. Then, follow the steps outlined on Onion's [website](https://onion.io/omega2-lte-guide/) to complete setup. Ensure that your Onion has both WiFi and LTE working properly before proceeding.

Optionally, you may wish to use the provided SteelEagle [STL files](https://github.com/cmusatyalab/steel-eagle/tree/main/stl/) to print our custom harness for the Onion. Follow these [instructions]({{ site.baseurl }}{% link stl.md %}) for more details.

### Software Configuration
Navigate to the root directory of the SteelEagle [repository](https://github.com/cmusatyalab/steel-eagle/tree/main) on your computer. Once there, in your terminal, run `cd onboard/onion/device`. You should see one file in this directory, `onion_steup.sh`. Move this to the Onion by first connecting to the device's WiFi hotspot, then running `scp onion_setup.sh root@omega-XXXX.local:~/` where `XXXX` corresponds to the ID of your Onion (you can find this by looking at its hotspot name). The default password is `onioneer`.

Once you have copied the setup script to the Onion, run `ssh root@omega-XXXX.local` on your computer to login. Install Wireguard on the device by running `opkg --force-depends install wireguard`. Then, run `./onion_setup.sh`. Run `ls -ltrh`. You should see four new Wireguard configuration files, named `Alpha.conf`, `Bravo.conf`, `Charlie.conf`, and `Delta.conf`. These files are used to open Wireguard tunnels to talk to the Onion and the drone when in flight. It is *highly recommended* that you purchase a static IP SIM card to use with the Onion. If you do not do this, you will have to modify the configuration file on the server every time the Onion is power cycled or disconnects.

On your computer, run `scp root@omega-XXXX.local:~/X.conf .` where `X.conf` can refer to any one of the four configuration files. Then, move this file to the server under `/etc/wireguard`. Keep in mind that this directory requires root to access. Setup of the Onion is now complete and you can proceed to setting up the backend.

The full command list is as follows:
```
cd /path/to/steel-eagle/onboard/onion/device
scp onion_setup.sh root@omega-XXXX.local:~/
ssh root@omega-XXXX.local
opkg --force-depends install wireguard
./onion_setup.sh
exit
scp root@omega-XXXX.local:~/X.conf .
sudo mv ~/X.conf /etc/wireguard
```
