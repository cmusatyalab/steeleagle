---
layout: default
title: Home
nav_order: 1
permalink: /
---

# Overview

SteelEagle is a software suite that enables the conversion of recreational, consumer-off-the-shelf (COTS) drones to intelligent, beyond-visual-line-of-sight (BVLOS), fully-autonomous aircraft. This allows users to develop complex autonomous UAV applications without needing to purchase or configure expensive aircraft hardware. SteelEagle drones are easy to deploy and importantly, are drone agnostic. This means that SteelEagle can be adapted to work with any drone control API, as long as it supports control over WiFi.

## Features
1. **Low Cost**: SteelEagle uses cheap photography drones like the Parrot Anafi (<$500) which are much less expensive than even the cheapest fully-autonomous COTS drones ($3,000+).
2. **Ease of Use**: SteelEagle drones are designed to abstract away as much low-level control code as possible allowing users to focus on developing higher level tasks.
3. **Lightweight**: SteelEagle enables autonomy on drones significantly smaller and lighter than traditional autonomous drones by offloading computation to the edge/cloud.
4. **Portable**: SteelEagle is drone agnostic by design, able to accomodate any drone with a WiFi or LTE control API.
5. **BVLOS**: SteelEagle drones support autonomous or manual control wherever there is LTE service, even beyond visual line of sight.
6. **Access to Powerful Computation**: SteelEagle drones have access to much more powerful computation over the network than most drones have onboard.

## Drawbacks
1. **No Disconnected Operation**: By default, SteelEagle drones do not currently support extended disconnected operation.
2. **High Latency**: Video and telemetry streams are highly latent because of network transmission delays.
3. **Limited Compatibility with GCS**: Because of the way SteelEagle's architecture, it is difficult to integrate it with existing ground control stations like QGroundControl. We have provided our own ground control software for this purpose.


