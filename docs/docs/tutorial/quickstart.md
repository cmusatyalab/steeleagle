---
sidebar_position: 2
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Quickstart

This guide will get you started with your first simulated flight of SteelEagle in under 5 minutes!

## Installation

First, clone the SteelEagle repository:

<Tabs>
  <TabItem value="https" label="HTTPS">
  ```bash
  git clone https://github.com/cmusatyalab/steeleagle.git
  ```
  </TabItem>
  <TabItem value="ssh" label="SSH" default>
  ```bash
  git clone git@github.com:cmusatyalab/steeleagle.git
  ```
  </TabItem>
</Tabs>

Then, download [UV](https://docs.astral.sh/uv/) from Astral's website. UV is a Python package management tool that wraps over pip.
It makes it easy to download required dependencies within a virtual environment with minimal setup.

<Tabs>
  <TabItem value="macoslinux" label="MacOS and Linux">
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
  </TabItem>
  <TabItem value="windows" label="Windows" default>
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
  </TabItem>
</Tabs>

If on Mac or Linux, be sure to run the commands listed in the install output to source UV into your system path.

## Setup

To run SteelEagle, you must have a backend and at least one vehicle set up. For this guide, we will create a simulated
vehicle and spin up a minimal backend that reports telemetry back to the GCS.

### Backend Setup

SteelEagle provides a backend setup wizard to streamline the backend setup process.

### Vehicle Setup

Navigate to the `vehicle/` directory within `steeleagle`. Then, copy the `config.template.toml` file to `config.toml`.
This is the configuration file that the vehicle will use when running. There are four important fields you must set before running.
There are:
- `name`: the name of the vehicle reported by telemetry; this is the name that will appear on the GCS
- `package`: the driver package you want to run, in this case `steeleagle-sim`
- `swarm_controller`: the IP address where your swarm controller is running (in most cases, this will be where the rest of your backend is);
for instance, `localhost:5003` if it is running on the same computer as the vehicle
- `remote_compute_service`: the IP address where your compute service is running (in most cases, this will be where the rest of your backend is);
for instance, `localhost:9099` if it is running on the same computer as the vehicle

```yaml
[vehicle]
# Name of the vehicle reported through telemetry
// highlight-next-line
name = 'Simulated Drone'
# Vehicle package (see https://git.cmusatyalab.org/steeleagle/roost for list of available vehicles)
// highlight-next-line
package = 'steeleagle-sim'
[vehicle.kwargs]

[cloudlet]
# Location of the swarm controller (typically runs on port 5003)
// highlight-next-line
swarm_controller = 'localhost:5003'
# Location of the remote Gabriel server (typically runs on port 9099)
// highlight-next-line
remote_compute_service = 'localhost:9099'

[logging]
# Whether or not to create an MCAP flight log for mission replay
generate_flight_log = true
# Log to a custom filename; otherwise will autogenerate
# a name based on name, date, and time if empty string
# is provided
custom_filename = ''
# Path to log file
file_path = 'kernel/logs/'
# Log level
log_level = 'INFO'
```

Once done, run `uv run launch.py` and the vehicle should start!

## Controlling the Vehicle

After the vehicle connects to the backend, open the GCS by going to your browser and navigating to the URL of your backend, port 8501.
Then, switch to the Control tab. You should see your vehicle in the list of available vehicles. Select it, arm, then takeoff by pressing `T`.
You can control the vehicle using `W`, `A`, `S`, `D` for planar movement, `J`, `K` for rotation, and `I`, `K` for elevation.
