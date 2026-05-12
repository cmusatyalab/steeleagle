# SteelEagle CLI for orchestration

## Prerequisites


* Follow the instructions the [quickstart](https://cmusatyalab.github.io/steeleagle/tutorial/quickstart) to install uv, docker, and NVIDIA drivers.
__NOTE: If uv, docker, and NVIDIA drivers are already present on the system, only the setup wizard needs to be run.__

* Run the [setup_wizard.py](https://cmusatyalab.github.io/steeleagle/tutorial/quickstart#environment-setup) to generate the configuration files for the backend.

Once the setup wizard is complete, the rest of the Quickstart guide can be ignored and the following sections in this README can be followed.

## Tool Installation

To install the orchestration CLI, referred to as "steele", use uv:

```bash
cd ~/steeleagle/orchestration
uv tool install . -e
```


## Start the CLI daemon

Before any other commands can be executed, the daemon must be launched. This command is blocking, so it will need to be run in a separate terminal, or pushed into the background (with &).

```bash
steele daemon
```

## Install zero or more drivers

The driver subcommand can be used to list or install available SteelEagle drivers. If no additional drivers are installed, only simulated Aviary drones can be launched.

```bash
steele driver list
```

And to install (e.g. the Parrot ANAFI drivers)...

```bash
steele driver install parrot-base
steele driver install parrot-anafi
```

> [!NOTE]
> The parrot-anafi driver is dependent upon parrot-base driver, thus they both need to be installed.

## Install/build GCS

The 'gcs install' command will install nvm/npm and build the React frontend for the GCS.  There is also a separate build command that can be run if changes are ever made to the frontend.

```bash
steele gcs install
```


## List SteelEagle services

```bash
steele services
```


## Service Status
To see the status of all services use `ps`. The details flag will show a breakdown of individual container/process status information:

```bash
steele ps
steele ps --details
```
## Starting/stopping/restarting/logging services

Each of the services has its own subcommand with 4 main functions: start, stop, restart, and logs. For instance, to start all 4 services (which includes one simulated Aviary drone)

```bash
steele gcs start
steele sim start
steele backend start
steele vehicle start --name test1 --config test1.config.toml --internal test1.internal.toml --headless
```

> [!IMPORTANT]
> The backend will download container images needed to satisfy what is specified in the docker-compose.yml file which may take quite a while. Once the images are cached, starting the backend will be quicker.

> [!WARNING]
> If using a simulated vehicle from Aviary, the sim must be started before the vehicle or it will fail to connect.


Logs can be retrieved for a particular service. The -f flag can be used to follow the logs while -n will limit the number of lines returned.

```bash
steele gcs logs -f
steele vehicle logs test1 -n 100
```
