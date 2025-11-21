---
sidebar_position: 2
---

# Backend Setup

The tutorial will step through the setup of SteelEagle backend components. Most of these components have published [Docker image](https://hub.docker.com) that are built using Github actions when the Github repository is updated. We use docker compose to manage the container instances and the network between them.

## Prerequisites

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

Next, clone the SteelEagle repository from GitHub:

```bash
git clone --depth 1 https://github.com/cmusatyalab/steeleagle.git
cd steeleagle
```

Finally, install `uv` which is used to install and manage requirements for SteelEagle components:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Environment Setup

The backend code for SteelEagle lives in the `backend` directory. Under `backend/server` there is a setup_wizard.py script which will configure the environment

```bash
backend
└── server
    ├── docker-compose.yml
    └── engines
 ...
    ├── setup_wizard.py
```

To launch the setup wizard, we will use `uv`, which will create a virtual environment for all the dependencies, install them, and then run the script:

```bash
uv run setup_wizard.py
```
<div style={{textAlign: 'center'}}>
![SteelEagle Architecture](/img/wizard/setup_wizard1.png)
</div>

The wizard will first ask if the default configuration should be used. The default values will be displayed in the dialog box. If the defaults are used, no other prompts will be shown and the configuration files will be written. If not, the wizard will walk through configuration for rest of the components.

<div style={{textAlign: 'center'}}>
![SteelEagle Architecture](/img/wizard/setup_wizard2.png)
</div>

Once the wizard is complete, 3 configuration files will be written:

* `backend/server/.env` - This file contains the majority of the variables for each of the containers in the docker-compose.yml file
* `backend/server/redis/redis.conf` - configuration for the redis db
* `gcs/streamlit/.streamlit/secrets.toml` - Streamlit uses these secrets to connect to the other components of the backend

:::note

In the default values are used, the setup wizard will download a YOLOv5m COCO model for use by the detection engine. If you want to use a custom object detection model, place it in the `backend/server/models` directory and enter the filename when prompted during the setup wizard.

:::


## Launch with docker compose

The `docker-compose.yml` file is pre-configured to launch the required
backend computation engines and expose the ports needed to allow for
communication between components.

We recommend using tmux to create multiple windows so it is easier to view logs while also starting/stopping components.

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

## Start Streamlit GCS

The Streamlit app can be launched using `uv`. We specify overview.py as the entrypoint to the Streamlit application.

```bash
cd ~/steeleagle/gcs/streamlit
uv run streamlit run overview.py
```

Once Streamlit is running, the app will run at http://localhost:8501. Enter the password that was configured during the setup wizard.
