# Onboard Task-Switch FlightScript Tutorial

This tutorial covers the latest update for the onboard Task-Switch FlightScript, specifically targeting the `hermes/python` directory, `hermes.py`, and `supervisor.py`.

## Logistics

### New Directories

Under `hermes/python/`, three new directories have been added:

- `mission/`
- `task_defs/`
- `transition_defs/`



### Work Flow:

1. **Initialize the Mission Controller**: The supervisor is responsible for creating the Mission Controller, which will manage the drone's operations.
2. **Start the Mission**: The Mission Controller initiates the mission by sending a command for the drone to take off, marking the beginning of its operational phase.
3. **Create the Task Runner**: Alongside initiating the mission, the Mission Controller also establishes a Task Runner. The Task Runner is responsible for executing tasks that are queued up for the drone.
4. **Queue the First Task**: The Mission Controller queues the first task into the task queue, which is then picked up by the Task Runner for execution.
5. **Create Transitions for Task Monitoring**: As each task is created and queued, corresponding transitions are also established. These transitions are designed to constantly monitor the drone's environment to check if specific trigger conditions are met.
6. **Monitor Environment and Trigger Conditions**: The transitions continuously assess the environment based on the data captured by the drone. They check against predefined trigger conditions to determine if a transition is necessary.
7. **Signal Trigger Events**: When a trigger condition is met, the transition sends a signal back to the Mission Controller, indicating that the current task may need to be adjusted based on the new conditions.
8. **Switch Tasks Based on Conditions**: Upon receiving a signal that a trigger condition has been met, the Mission Controller evaluates the situation and switches the drone's task as needed. This ensures the mission adapts to changing conditions in real-time.

 <img src="https://documents.lucid.app/documents/036d65a8-1197-41e7-9e98-4f0be76c5665/pages/0_0?a=5683&x=489&y=4271&w=1213&h=1519&store=1&accept=image%2F*&auth=LCA%205e21fa4e462d85a6f108ccf7154ab48a3fab918dcbf5ce8fa978358fe023fb44-ts%3D1708724405" alt="img" style="zoom:67%;" />

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