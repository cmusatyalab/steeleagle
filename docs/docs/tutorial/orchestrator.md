---
sidebar_position: 3
---

# Orchestrator

The SteelEagle Orchestrator (the `steele` CLI, backed by a `steeld` daemon) manages the lifecycle of every SteelEagle service — the GCS, the backend containers, one or more vehicles, and the Aviary simulator — from a single tool, instead of opening a separate terminal for each component as described in the rest of the [Quickstart](quickstart). It is entirely optional: any service can still be started manually as shown elsewhere in these docs.

:::info
In the SteelEagle repo, the orchestrator lives at __~/steeleagle/orchestration__.
:::

## Prerequisites

* Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
* If you plan to manage and run the backend SteelEagle services, follow the [Quickstart](quickstart) to install Docker, CUDA/NVIDIA drivers, and the NVIDIA container toolkit.

:::note
If Docker and CUDA are already present on the system, only the setup wizard below needs to be run.
:::

* Run the [setup wizard](quickstart#environment-setup) to generate the configuration files for the backend.

Once the setup wizard is complete, the rest of the Quickstart guide can be skipped in favor of the sections below.

## Tool Installation

To install the orchestration CLI for the __current user__ (referred to below as "steele"), use uv:

```bash
cd ~/steeleagle/orchestration
uv tool install . -e
```

To install the CLI __system-wide__ (requires sudo privilege):

```bash
cd ~/steeleagle/orchestration
sudo UV_TOOL_DIR="/usr/local/share/uv/tools" UV_TOOL_BIN_DIR="/usr/local/bin" uv tool install -e .
```

## Service Configuration

The `orchestrator.yaml` file lists the services that the daemon should manage and the paths to those services. Modify this file to remove any services that don't need to be managed (e.g. set `sim`, `gcs`, and `backend` to `managed: false` if you only plan to run the vehicle on this system) and to set the paths to those services. By default, the configuration assumes the main SteelEagle repository is at `~/steeleagle` and the Roost repository is at `~/roost`. If these repositories were cloned to other locations, update `orchestrator.yaml` accordingly.

:::warning
If you plan to install the daemon as a system-wide service (i.e. running as root), the paths to the services should be absolute, lest they point at `/root` after user expansion instead of the user's home directory.
:::

```yaml
services:
  # Aviary Simulator (from git.cmusatyalab.org/steeleagle/roost)
  sim:
    managed: true
    type: process
    command: [
                "uv",
                "run",
                "--directory",
                "~/roost/aviary/src/steeleagle_aviary",
                "simulator.py",
            ]

  # React/FastAPI Ground Control System
  gcs:
    managed: true
    type: process
    command: [
                "uv",
                "run",
                "--directory",
                "~/steeleagle/gcs/react/backend",
                "main.py",
            ]

  # Backend containers including swarm controller and cognitive engines
  backend:
    managed: true
    type: compose
    compose_files: ["~/steeleagle/backend/server/docker-compose.yml"]
    environment: ["~/steeleagle/backend/server/.env"]

  # Vehicle (kernel, driver, mission) instances
  vehicle:
    managed: true
    type: pool
    command: [
                "uv",
                "run",
                "--directory",
                "~/steeleagle/vehicle",
                "launch.py",
            ]
```

## Install as a systemd service

The orchestrator daemon can be installed as a systemd service, either system-wide (with root permission) or at the user level. The CLI can be used to install the systemd unit file.

At user-level:

```bash
steele daemon install --user
```

System-wide (sudo required):

```bash
sudo steele daemon install
```

:::tip
Use the `--dry-run` flag to view the unit file that would be written without making any changes.
:::

## Start the CLI daemon

### Using systemd

If the orchestrator has been installed as a systemd unit, it can be started using `systemctl`:

```bash
# if installed at user level
systemctl --user start steeld
# system-wide service
sudo systemctl start steeld
```

### Manually

If the orchestrator is not installed as a service, it can be launched manually:

```bash
steele daemon --config /path/to/orchestrator.yaml
```

:::note
This command is blocking, so it needs to be run in a separate terminal, or pushed into the background (with `&`).
:::

## Install zero or more drivers

The `driver` subcommand lists or installs available SteelEagle drivers. If no additional drivers are installed, only simulated Aviary drones can be launched.

```bash
steele driver list
```

And to install (e.g. the Parrot ANAFI drivers):

```bash
steele driver install parrot-base
steele driver install parrot-anafi
```

:::note
The `parrot-anafi` driver depends on the `parrot-base` driver, so both need to be installed.
:::

## Install/build GCS

The `gcs install` command installs nvm/npm and builds the React frontend for the GCS. A separate `build` command can be run if changes are ever made to the frontend.

```bash
steele gcs install
```

## List SteelEagle services

```bash
steele services
```

## Service Status

To see the status of all services, use `ps`. The `--details` flag shows a breakdown of individual container/process status information:

```bash
steele ps
steele ps --details
```

## Starting/stopping/restarting/logging services

Each service has its own subcommand with 4 main functions: `start`, `stop`, `restart`, and `logs`. For instance, to start all 4 services (which includes one simulated Aviary drone):

```bash
steele gcs start
steele sim start
steele backend start
steele vehicle start --name test1 --config test1.config.toml --internal test1.internal.toml --headless
```

:::note
The backend will download container images needed to satisfy what is specified in the `docker-compose.yml` file, which may take quite a while. Once the images are cached, starting the backend will be quicker.
:::

:::warning
If using a simulated vehicle from Aviary, the sim must be started before the vehicle or it will fail to connect.
:::

Logs can be retrieved for a particular service. The `-f` flag follows the logs while `-n` limits the number of lines returned.

```bash
steele gcs logs -f
steele vehicle logs test1 -n 100
```
