---
layout: default
title: Harness Printing
nav_order: 6
has_children: false
permalink: docs/stl
---

# Harness Printing

In order to get our payloads (either the Samsung Galaxy 4 Watch or the Onion Omega LTE) to be carried by the ANAFI drones, we have created a number of modular pieces that can be printed and fused together using [Gloop](https://www.3dgloop.com/). We printed our harnesses in PLA, but prtining in ABS should also work, provided you get the correct version of Gloop.

_NOTE: The ANAFI has a payload capacity of 60g, so the harness needs to be very light in order for the harness + watch or harness + onion to be below this threshold._

## SCAD

We used OpenSCAD to allow us to programmatically generate individual .stl files which can then be sent to a printer. OpenSCAD can be installed with apt:

```sh
$ sudo apt-get install openscad
```
Unless you are modifying the ANAFI designs to print a harness for a different model drone, you should not need to change any of the .scad files in the /stl directory.

## Components for Galaxy Watch 4

* lite_body_clip.stl ***OR*** anafi_usa_body_clip.stl (Depending on whether you are printing for ANAFI or ANAFI USA)
* lite_watch_case.stl
* lite_watch_cap.stl

## Components for Onion Omega LTE

* lite_body_clip.stl ***OR*** anafi_usa_body_clip.stl (Depending on whether you are printing for ANAFI or ANAFI USA)
* drone_onion_lid.stl
* drone_onion.stl


## 3D Printer Settings

Since we are optimizing for weight, we have used almost no infill. The .stl files listed above should already be arranged to reduce the amount of support material that is needed.

## Assembly

### Watch

![Watch Assembly!](commander_layout.png)

### Onion

![Onion Assembly!](commander_layout.png)

_NOTE: The LTE module on the Onion Omega can interfere with the GPS of the ANAFI which is near the camera/gimbal. As such, care must be taken to orient the case properly and as far back on the clip as possible when Glooping the pieces together._

  
