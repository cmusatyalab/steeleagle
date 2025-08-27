As long as it adheres to the SteelEagle control plane [protocol](https://github.com/cmusatyalab/steeleagle/blob/main/protocol/controlplane.proto), interacts with the swarm controller over [ZeroMQ](https://zeromq.org/), and fetches data from the backend's Redis instance, the SteelEagle GCS could be reenvisioned.

## Reading Telemetry from Redis

Telemetry data from vehicles, as well as output from various cognitive engines (i.e. object detection results) are stored in Redis. Some of the data is ephemeral and is cleaned up by Redis itself using TTLs (time-to-live) to keep tables from growing to large.

### Keys

* __HASH drone:<drone_name>__ - These HASH keys hold slow-changing data about each vehicle that has connected to the system. i.e. Battery level, home location, alerts (magnetometer, satellites) The TTL is 7 days and is refreshed as long as heartbeats are sent from the vehicle.
* __STREAM telemetry:<drone_name>__ - There is also an associated STREAM key for each vehicle which stores the last 24 hours of telemetry data. These keys can become quite large depending on the rate at which telemetry is sent from the vehicle.  It contains highly volitile fields such as latitude, longitude, altitude, body velocity, gimbal body position, etc.
* __SORTED SET detections__ - This is a geohash table (specialized SORTED SET) that holds the geographic location of objects that are found by the object detection engine. Unique objects (per class) within a 5m radius are given an object id in the form <class>:<4-digit hex id> and an associated HASH table for that object is created which includes the metadata for this detection. See below.
* __HASH objects:<object_id>__ - These hash tables contain metadat for the detected object such as the time last seen, the drone which found it, the object class, its confidence, and a link to the image which contains bounding boxes.

## Reading Imagery from the Filesystem

Imagery is stored in the steeleagle-vol directory under `steeleagle/backend/server/`.  The directory structure is as follows (with annotations):

```bash
backend
└── server
    └── steeleagle-vol
        └── raw # raw images from the vehicles' streams
            └── droneA # separate directory for each vehicle
                └── 01-Jan-1900 # new directory created for each day
                    └── <timestamp>.jpg # files written at the timestamp they were received
                └── latest.jpg # the latest image for this vehicle
            └── droneB
            └── droneC
        └── detected # output from the object detection engine
            └── classes # symlinked files organized by class name
                └── person
                └── car
            └── drones # per vehicle detections
                └── droneA # separate directory for each vehicle
                    └── <timestamp>.jpg # files written at the timestamp they were received
                    ...
                    └── latest.jpg # the latest detection from this vehicle's stream
                └── droneB
                └── droneC
        └── moa # output from the monocular obstacle avoidance engine
            └── <timestamp>.jpg # files written at the timestamp they were received
            └── latest.jpg # the latest output from the obstacle avoidance engine

```

## Sending Commands via ZMQ

In order to actuate one or more vehicles, either manually or autonomously, commands from the GCS must be sent to the swarm controller running on the backend. The swarm controller will then deliver the command(s) to the hub process of the specified vehicles. This control plane is communicated over a ZMQ REQ/REP socket. The commands that can be sent are defined in [control_plane.proto](https://github.com/cmusatyalab/steeleagle/blob/main/protocol/controlplane.proto). The basic steps are as follows:

  1. Make a controlplane.Request message.
  2. Create a VehicleControl, MissionControl, or ComputeControl submessage and set the desired fields
  4. Send the serialized message over ZMQ to the swarm controller.


The following example is an excerpt from the streamlit GCS' [control.py](https://github.com/cmusatyalab/steeleagle/blob/main/gcs/streamlit/pages/control.py).

```python
import protocol.common_pb2 as common
import protocol.controlplane_pb2 as controlplane

...

req = controlplane.Request()
req.seq_num = int(time.time())
req.timestamp.GetCurrentTime()
for d in st.session_state.selected_drones:
    req.veh.drone_ids.append(d)

...

req.veh.gimbal_pose.pitch = st.session_state.gimbal_abs
req.veh.gimbal_pose.control_mode = (
    common.PoseControlMode.POSITION_ABSOLUTE
)

st.session_state.zmq.send(req.SerializeToString())
rep = st.session_state.zmq.recv()
```
