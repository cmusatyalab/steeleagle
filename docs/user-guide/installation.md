---
layout: default
title: Installation
parent: User Guide
nav_order: 2
permalink: docs/user-guide/install
---
# Installation
Clone the SteelEagle [repository](https://github.com/cmusatyalab/steel-eagle/tree/main). Then, on your smartphone, install Parrot FreeFlight 6 which is available on both the [Apple App Store](https://apps.apple.com/us/app/freeflight-6/id1386165299) and [Google Play Store](https://play.google.com/store/apps/details?id=com.parrot.freeflight6&hl=en_US&gl=US&pli=1). Next, decide on a control environment: Python (Onion) or Java (smartwatch). There are advantages and disadvantages to both methods. Once you select the environment you want, follow the associated instructions below.

<div class="comparison" markdown="1">
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
</div>

## Python Environment
This section will describe how to configure the [Onion Omega 2 LTE](https://onion.io/store/omega2-lte-na/) to work with SteelEagle. Ensure that you have purchased the necessary materials outlined in the [requirements section]({{ site.baseurl }}{% link user-guide/requirements.md %}).

### Hardware Preparation
Insert a working compatible SIM card into your Onion Omega 2 LTE and attach the two LTE antennas to the ports labelled 4G and 4G DIV. Then, follow the steps outlined on Onion's [website](https://onion.io/omega2-lte-guide/) to complete setup. Ensure that your Onion has both WiFi and LTE working properly before proceeding.

Optionally, you may wish to use the provided SteelEagle [STL files](https://github.com/cmusatyalab/steel-eagle/tree/main/stl/) to print our custom harness for the Onion. Follow these [instructions]({{ site.baseurl }}{% link stl.md %}) for more details.

### Software Installation
First, install Parrot Olympe by [following the steps provided on Parrot's website](https://developer.parrot.com/docs/olympe/installation.html). Then, navigate to the root directory of the SteelEagle [repository](https://github.com/cmusatyalab/steel-eagle/tree/main).

### Verification

### Parrot GroundSDK
Parrot GroundSDK will be installed automatically when you build the control app on the Galaxy Watch. It is not necessary to build it separately.

## Hardware
 

