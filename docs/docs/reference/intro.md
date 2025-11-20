---
sidebar_position: 1
---

# SteelEagle Architecture

<div style={{textAlign: 'center'}}>
![SteelEagle Architecture](/img/ref/steeleaglev3.0-arch.png)
</div>

SteelEagle is comprised of two large systems each with a number of specific components.

## SteelEagle OS

The SteelEagle OS is the entity that interacts with vehicle hardware, runs the autonomous mission logic, and interfaces with the backend server. Depending on the vehicle hardware, its payload capacity, and the communication protocols it uses, the SteelEagle OS may run onboard the vehicle, on the remote controller that is connected to the vehicle, or on the backend, however, logically this entity can be thought of as running 'on board'. Below is a short description of the components of the SteelEagle OS:

* Drone Driver - Communicates with the vehicle autopilot software using whatever proprietary method is required to receive telemetry/imagery and to transform SteelEagle commands into their vehicle-specific counterparts.
* Local Compute Driver - Interfaces with any compute engines that may be on board the vehicle to get local results.
* Kernel - Handles the core GRPC services for communication between components and the backend.
* Mission Logic - Executes the autonomous mission and is responsible for managing state transitions that are triggered by events.
* Remote Compute Driver - Using the [Gabriel](https://github.com/cmusatyalab/gabriel) protocol, the remote compute driver sends compute requests to the cogntive engines that are running on the backend. Results from those engines are then sent back to the kernel.

## Backend Server (Cloudlet)

The backend entity in SteelEagle provides command and control functionality for all connected vehicles and also provides various AI capabilities through the cogntivie engines that are running there. For example, the engines may provide object detection results or depth information to all connected vehicles for them to act upon. Below is a short description of the backend components:

* Gabriel Server - Token-based flow control of incoming sensor data from all connected vehicles. Relays frames to cogntive engines for processing and returns results to vehicles
* Cognitive Engines - Performs AI functions on incoming sensor data such as object detection, monocular obstacle avoidance, SLAM, et cetera
* Swarm Controller (Control Plane Module) - Interfaces with the GRPC services running in each vehicle's SteelEagle OS to relay control plane information such as manual flight control, autonomous mission upload/start/stop,  et cetera
* Redis - Telemetry data cache for GCS and historical analytics
* GCS - Streamlit-based control service to manage and control connected vehicles
