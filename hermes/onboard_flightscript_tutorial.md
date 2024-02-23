# Onboard Task-Switch FlightScript Tutorial

This tutorial covers the latest update for the onboard Task-Switch FlightScript, specifically targeting the `hermes/python` directory, `hermes.py`, and `supervisor.py`.

## Logistics

### New Directories

Under `hermes/python/`, three new directories have been added:

- `mission/`
- `task_defs/`
- `transition_defs/`

### Mission

The mission directory contains the following key components:

#### `MissionController.py`

- **Purpose**: Controls the entire flight mission.
- core functions:
  - Starts the mission by creating the task runner and commands the drone to take off.
  - Switches the task based on triggered events from the transitions of the current task.
  - Ends the mission by terminating the task runner and commanding the drone to return home.

#### `TaskRunner.py`

- **Purpose**: Managed by the mission controller to run or stop tasks.
- core functions:
  - Manages a task queue, executing tasks as they are added.
  - Supports stopping the current task and queuing a new task.

#### `MissionCreator.py`

- **Purpose**: Auto-generated file specifying the concrete mission, created by the droneDSL.

### Task_defs

Contains implementations for various task types, such as:

- Detect Task
- Track Task

Each task manages a list of all active transitions.

### Transition_defs

Includes implementations for transition types, such as:

- Timeout
- Object Detection

## Instructions

### Setup Simulator Environment

1. Start Sphinx simulator with the specified drone model:

   ```
   sphinx "/opt/parrot-sphinx/usr/share/sphinx/drones/anafi.drone"::firmware="https://firmware.parrot.com/Versions/anafi/pc/%23latest/images/anafi-pc.ext2.zip"
   ```

2. Use 

   ```
   parrot-ue4-sphx-tests
   ```

    to set GPS coordinates and paths:

   ```
   parrot-ue4-sphx-tests -gps-json='{"lat_deg":40.4156235, "lng_deg":-79.9504726 , "elevation":1.5}'
   ```

3. Add `MissionCreator.py` to the `mission/` directory.

### Deploy with Hermes

1. Zip the files using hermes:

   ```
   python3 hermes.py -p python -v
   ```

### Initialize Commander and Supervisor

1. Start the commander interface:

   ```
   python3 gui_commander_adapter.py
   ```

2. Initialize the supervisor with cloudlet support:

   ```
   python3 supervisor.py -s <cloudlet> -S
   ```