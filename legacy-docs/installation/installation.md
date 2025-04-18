---
layout: default
title: Installation
nav_order: 2
has_children: true
permalink: docs/install
---
# Requirements

## Software
SteelEagle was tested and implemented on Ubuntu 22.04 machines. It is not guaranteed to work with other distributions, although it should be compatible with older Debian distributions with slight modifications. Windows and MacOS are both officially unsupported but may work with more significant modifications.

## Hardware
This tutorial assumes that you possess:
1. A [Parrot Anafi](https://www.parrot.com/us/drones/anafi) drone (for hardware-in-the-loop (HITL) testing).
2. A publicly addressable Ubuntu 22.04 server (optional but recommended).
3. An Ubuntu 22.04 laptop (optional but recommended).
4. A smartphone to set up the Galaxy Watch 4 (may not be necessary on all watches) and connect to the drone.
5. A [Galaxy Watch 4](https://www.samsung.com/us/watches/galaxy-watch4/buy/) or equivalent Android smartwatch with LTE (optional but necessary for Java HITL).
6. An [Onion Omega 2 LTE](https://onion.io/store/omega2-lte-na/) with a SIM card, two LTE antennas, and a small LiPo (optional but necessary for Python HITL).

The minimum requirement to complete this tutorial is an Ubuntu 22.04 computer with a connected display and strong integrated graphics or a dedicated GPU. However, completing the tutorial in this way will not simulate LTE network conditions and real world computation limitations. Thus it is strongly suggested that you either purchase components for HITL Python or Java simulation.

## Hardware-in-the-Loop Purchase Guide (Optional)
Hardware-in-the-Loop (HITL) simulation will allow you to simulate the entire SteelEagle ecosystem and will better prepare you for real world flight operations. It is *highly recommended* that you complete either a walkthrough of the Python HITL or Java HITL tutorial prior to your first flight.

### Python HITL
Python HITL on the Parrot Anafi uses the [Onion Omega 2 LTE](https://onion.io/store/omega2-lte-na/), a single-board Linux router that runs OpenWRT. The Omega 2 LTE does not have its own power supply or antennas, so these must be purchased separately.

The following purchases are recommended:
1. 1 x [Onion Omega 2 LTE](https://www.mouser.com/ProductDetail/Onion/OM-O2LTE-NA?qs=yqaQSyyJnNhhcT0W%2FqC0PA%3D%3D). The link provided is for the North America version. If you are not based in North America, please purchase the version for your region.
2. 1 x SIM card. It is *highly recommended* that you purchase a static IP SIM card to work with the Onion although it is not mandatory. Keep in mind that the Onion has *extremely high* data usage since it offloads its 720p30fps (~3 Mbps bitrate) encoded stream entirely over LTE. You will almost certainly need a custom data plan for this SIM. If data rates are a concern, consider using the Galaxy Watch/Java API which transmits at a much lower bitrate.
3. 2 x [Molex Antennas](https://www.digikey.com/en/products/detail/molex/2125700100/10489644?utm_adgroup=&utm_source=google&utm_medium=cpc&utm_campaign=PMax%20Shopping_Product_Medium%20ROAS%20Categories&utm_term=&utm_content=&utm_id=go_cmp-20223376311_adg-_ad-__dev-c_ext-_prd-10489644_sig-Cj0KCQiApOyqBhDlARIsAGfnyMpPNSWaUFj4HC3CYBlANHco_McIhH5QFS9G4orVkqNVrHP24MXEUVgaAh4mEALw_wcB&gad_source=1&gclid=Cj0KCQiApOyqBhDlARIsAGfnyMpPNSWaUFj4HC3CYBlANHco_McIhH5QFS9G4orVkqNVrHP24MXEUVgaAh4mEALw_wcB) (or equivalent). Any lightweight, small ultra-wideband 4G PCB antenna should work. *See below note*
4. 1 x [LiPo](https://www.adafruit.com/product/1578). Any lightweight, small LiPo should work. This battery will give the Onion enough battery life to last at least 20 minutes (the maximum flight time of the drone). *See below note*.

{: .note }

The Parrot Anafi has a safe payload cutoff of around 60g. If you deviate from the recommended purchases, make sure that the overall payload of the Onion, antennas, LiPo, and harness does not exceed this threshold.

### Java HITL
Java HITL on the Parrot Anafi uses the [Samsung Galaxy Watch 4](https://www.samsung.com/us/watches/galaxy-watch4/buy/) or an equivalent modern Android smartwatch with LTE connectivity (*see below note*). For the Galaxy Watch series and some other watches, a smartphone is required for initial setup and for configuring the watch ESIM. This tutorial assumes you are using the Samsung Galaxy Watch 4 but installation steps should be similar for other smartwatches.

{: .note }

The Parrot Anafi has a safe payload cutoff of around 60g. If you deviate from the recommended purchase, make sure that the overall payload of the watch and harness does not exceed this threshold.

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


 

