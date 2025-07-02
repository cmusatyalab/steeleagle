As long as it adheres to the SteelEagle control plane [protocol](https://github.com/cmusatyalab/steeleagle/blob/main/protocol/controlplane.proto), interacts with the swarm controller over [ZeroMQ](https://zeromq.org/), and fetches data from the backend's Redis instance, the SteelEagle GCS could be reenvisioned.

## Reading Telemetry from Redis

Telemetry data from vehicles, as well as output from various cognitive engines (i.e. object detection results) are stored in Redis. Some of the data is ephemeral and is cleaned up by Redis itself using TTLs (time-to-live) to keep tables from growing to large.

### Keys

* __HASH drone:<drone_name>__ - These HASH keys hold slow-changing data about each vehicle that has connected to the system. i.e. Battery level, home location, alerts (magnetometer, satellites) The TTL is 7 days and is refreshed as long as heartbeats are sent from the vehicle.
* __STREAM telemetry:<drone_name>__ - There is also an associated STREAM key for each vehicle which stores the last 24 hours of telemetry data. These keys can become quite large depending on the rate at which telemetry is sent from the vehicle.  It contains highly volitile fields such as latitude, longitude, altitude, body velocity, gimbal body position, etc.

## Reading Imagery from the Filesystem

## Sending Commands via ZMQ
