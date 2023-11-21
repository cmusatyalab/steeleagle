---
layout: default
title: Commander GUI (our GCS)
nav_order: 5
has_children: false
permalink: docs/commander
---

# Commander

## Description

Our command and control software, simply referred to as the **Commander**, is used to view stream and telemetry data from connected drones and to send them command message (e.g. manual control, return to home, send on autonomous mission). 
The current implementation runs in python and is based on [customtkinter](https://github.com/TomSchimansky/CustomTkinter).
An implementation using [streamlit](https://streamlit.io/) is a work-in-progress.

## Installation

The commander can be installed by simply installing the requirements: 

```sh
cd ~/steel-eagle/cnc/python-client/
python3 -m pip install requirements.txt
```

## Usage

```sh
cd ~/steel-eagle/cnc/python-client/
python3 gui_commander.py
```
