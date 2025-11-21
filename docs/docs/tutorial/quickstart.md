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
vehicle and spin up a backend containing an obstacle avoidance and object detection engine

### Backend Setup

SteelEagle provides a backend setup wizard to streamline the backend setup process.
Most backend components have published [Docker image](https://hub.docker.com) that are built using Github actions when the Github repository is updated. The Docker compose file in the backend folder is used to manage the container instances and the network between them.

#### Prerequisites

First, install [NVIDIA CUDA/drivers](https://developer.nvidia.com/cuda-downloads) and the [NVIDIA Container toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html#with-apt-ubuntu-debian).

Then install Docker and Docker Compose:

```bash
# 1. download the script
curl -fsSL https://get.docker.com -o install-docker.sh
# 2. verify the script's content
cat install-docker.sh
# 3. run the script with --dry-run to verify the steps it executes
sh install-docker.sh --dry-run
# 4. run the script either as root, or using sudo to perform the installation.
sudo sh install-docker.sh
```
#### Environment Setup

The backend code for SteelEagle lives in the `backend` directory. Under `backend/server` there is a setup_wizard.py script which will configure the environment

```bash
backend
└── server
    ├── docker-compose.yml
    └── engines
 ...
    ├── setup_wizard.py
```

To launch the setup wizard, use `uv`, which will create a virtual environment for all the dependencies, install them, and run the script. Use the following command:

```bash
uv run setup_wizard.py
```
<div style={{textAlign: 'center'}}>
![Setup Wizard Opening](/img/wizard/setup_wizard1.png)
</div>

The wizard will first ask if the default configuration should be used. The default values will be displayed in the dialog box. If the defaults are used, no other prompts will be shown and the configuration files will be written. If not, the wizard will walk through configuration for rest of the components.

<div style={{textAlign: 'center'}}>
![Setup Wizard Additional](/img/wizard/setup_wizard2.png)
</div>

Once the wizard is complete, 3 configuration files will be written:

* `backend/server/.env` - This file contains the majority of the variables for each of the containers in the docker-compose.yml file
* `backend/server/redis/redis.conf` - configuration for the redis db
* `gcs/streamlit/.streamlit/secrets.toml` - Streamlit uses these secrets to connect to the other components of the backend

:::note

In the default values are used, the setup wizard will download a YOLOv5m COCO model for use by the detection engine. If you want to use a custom object detection model, place it in the `backend/server/models` directory and enter the filename when prompted during the setup wizard.

:::

#### Launch with docker compose

The `docker-compose.yml` file is pre-configured to launch the required
backend computation engines and expose the ports needed to allow for
communication between components.

[Tmux](https://github.com/tmux/tmux/wiki) can be used to create multiple windows so it is easier to view logs while also starting/stopping components.

To launch the containers:

```bash
cd ~/steeleagle/backend/server
docker compose up -d
```

To stop __ALL__ the containers:
```bash
docker compose down
```

To stop and individual container:
```bash
docker compose stop <container_name>
```

To view logs for an individual container:
```bash
docker compose logs -f <container_name>
```

To create a minimal backend with just the telemetry engine, Redis DB, and the swarm controller:
```bash
docker compose up telemetry-engine redis swarm-controller gabriel-server http-server
```

:::warning

If running the minimal backend, you need to change the law file in `.laws.toml`, found in the `vehicle/`.

Change:
```yaml
[__BASE__]
enter = ['Compute.AddDatasinks|{"datasinks": [{"id": "telemetry"}, {"id": "object-engine"}, {"id": "obstacle-engine"}]}']
```
to:
```yaml
[__BASE__]
enter = ['Compute.AddDatasinks|{"datasinks": [{"id": "telemetry"}]}']
```
:::

#### Start Streamlit GCS

The Streamlit app can be launched using `uv`. We specify overview.py as the entrypoint to the Streamlit application.

```bash
cd ~/steeleagle/gcs/streamlit
uv run streamlit run overview.py
```

Once Streamlit is running, the app will run at `http://localhost:8501`. Enter the password that was configured during the setup wizard.

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
