---
toc_max_heading_level: 3
---

import Link from '@docusaurus/Link';

# telemetry 
---

## <><code class="docs-func">enum</code></> MotionStatus


Information about the motion of the vehicle.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;MOTORS_OFF**&nbsp;&nbsp;(`0`) <text>&#8212;</text> motors of the vehicle are off

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;RAMPING_UP**&nbsp;&nbsp;(`1`) <text>&#8212;</text> motors of the vehicle are ramping

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;IDLE**&nbsp;&nbsp;(`2`) <text>&#8212;</text> the vehicle is on but idle

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;IN_TRANSIT**&nbsp;&nbsp;(`3`) <text>&#8212;</text> the vehicle is in motion

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;RAMPING_DOWN**&nbsp;&nbsp;(`4`) <text>&#8212;</text> motors of the vehicle are ramping down


---
## <><code class="docs-func">enum</code></> ImagingSensorType


Imaging sensor types.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;RGB**&nbsp;&nbsp;(`0`) <text>&#8212;</text> RGB camera

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;STEREO**&nbsp;&nbsp;(`1`) <text>&#8212;</text> stereo camera

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;THERMAL**&nbsp;&nbsp;(`2`) <text>&#8212;</text> thermal camera

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;NIGHT**&nbsp;&nbsp;(`3`) <text>&#8212;</text> night vision camera

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;LIDAR**&nbsp;&nbsp;(`4`) <text>&#8212;</text> LIDAR sensor

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;RGBD**&nbsp;&nbsp;(`5`) <text>&#8212;</text> RGB-Depth camera

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;TOF**&nbsp;&nbsp;(`6`) <text>&#8212;</text> ToF (time of flight) camera

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;RADAR**&nbsp;&nbsp;(`7`) <text>&#8212;</text> RADAR sensor


---
## <><code class="docs-func">enum</code></> BatteryWarning


Battery warnings and alerts.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;NONE**&nbsp;&nbsp;(`0`) <text>&#8212;</text> the vehicle is above 30% battery

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;LOW**&nbsp;&nbsp;(`1`) <text>&#8212;</text> the vehicle is below 30% battery

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;CRITICAL**&nbsp;&nbsp;(`2`) <text>&#8212;</text> the vehicle is below 15% battery


---
## <><code class="docs-func">enum</code></> GPSWarning


GPS fix warnings and alerts.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;NO_GPS_WARNING**&nbsp;&nbsp;(`0`) <text>&#8212;</text> GPS readings are nominal and a fix has been achieved

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;WEAK_SIGNAL**&nbsp;&nbsp;(`1`) <text>&#8212;</text> weak GPS fix, expect errant global position data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;NO_FIX**&nbsp;&nbsp;(`2`) <text>&#8212;</text> no GPS fix


---
## <><code class="docs-func">enum</code></> MagnetometerWarning


Magnetometer warnings and alerts.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;NO_MAGNETOMETER_WARNING**&nbsp;&nbsp;(`0`) <text>&#8212;</text> magnetometer readings are nominal

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;PERTURBATION**&nbsp;&nbsp;(`1`) <text>&#8212;</text> the vehicle is experiencing magnetic perturbations


---
## <><code class="docs-func">enum</code></> ConnectionWarning


Connection warnings and alerts.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;NO_CONNECTION_WARNING**&nbsp;&nbsp;(`0`) <text>&#8212;</text> connection to remote server is nominal

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;DISCONNECTED**&nbsp;&nbsp;(`1`) <text>&#8212;</text> contact has been lost with the remote server

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;WEAK_CONNECTION**&nbsp;&nbsp;(`2`) <text>&#8212;</text> connection is experiencing interference or is weak


---
## <><code class="docs-func">enum</code></> CompassWarning


Compass warnings and alerts.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;NO_COMPASS_WARNING**&nbsp;&nbsp;(`0`) <text>&#8212;</text> absolute heading is nominal

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;WEAK_HEADING_LOCK**&nbsp;&nbsp;(`1`) <text>&#8212;</text> absolute heading is available but may be incorrect

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;NO_HEADING_LOCK**&nbsp;&nbsp;(`2`) <text>&#8212;</text> no absolute heading available from the vehicle


---
## <><code class="docs-func">enum</code></> MissionExecState


Execution state of the current mission.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;READY**&nbsp;&nbsp;(`0`) <text>&#8212;</text> mission is ready to be executed

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;IN_PROGRESS**&nbsp;&nbsp;(`1`) <text>&#8212;</text> mission is in progress

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;PAUSED**&nbsp;&nbsp;(`2`) <text>&#8212;</text> mission is paused

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;COMPLETED**&nbsp;&nbsp;(`3`) <text>&#8212;</text> mission has been completed

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;CANCELED**&nbsp;&nbsp;(`4`) <text>&#8212;</text> mission was cancelled


---
## <><code class="docs-func">message</code></> TelemetryStreamInfo


Information about the telemetry stream.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;current_frequency**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> current frequency of telemetry messages [Hz]

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;max_frequency**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> maximum frequency of telemetry messages [Hz]

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;uptime**&nbsp;&nbsp;(<code>/google/protobuf/Duration</code>) <text>&#8212;</text> uptime of the stream


---
## <><code class="docs-func">message</code></> BatteryInfo


Information about the vehicle battery.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;percentage**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> battery level [0-100]%


---
## <><code class="docs-func">message</code></> GPSInfo


Information about the vehicle GPS fix.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;satellites**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> number of satellites used in GPS fix


---
## <><code class="docs-func">message</code></> CommsInfo


Future: information about the vehicle's communication links.

---
## <><code class="docs-func">message</code></> VehicleInfo


Information about the vehicle.

This includes the name, make, model and its current status (battery, GPS, comms, motion).

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;name**&nbsp;&nbsp;(`string`) <text>&#8212;</text> the vehicle that this telemetry corresponds to

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;model**&nbsp;&nbsp;(`string`) <text>&#8212;</text> model of the vehicle

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;manufacturer**&nbsp;&nbsp;(`string`) <text>&#8212;</text> manufacturer of the vehicle

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;motion_status**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#enum-motionstatus">MotionStatus</Link></code>) <text>&#8212;</text> current status of the vehicle

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;battery_info**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-batteryinfo">BatteryInfo</Link></code>) <text>&#8212;</text> battery info for the vehicle

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;gps_info**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-gpsinfo">GPSInfo</Link></code>) <text>&#8212;</text> GPS sensor info for the vehicle

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;comms_info**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-commsinfo">CommsInfo</Link></code>) <text>&#8212;</text> communications info for the vehicle


---
## <><code class="docs-func">message</code></> SetpointInfo


Information about the current setpoint.

Provides the current setpoint for the vehicle. A setpoint is a position or velocity target
that the vehicle is currently moving towards. By default, when the vehicle is idle, this
setpoint is a `position_body_sp` object set to all zeros. The frame of reference for each
setpoint is implied by the name; e.g. velocity_neu_sp uses the NEU (North, East, Up)
reference frame and velocity_body_sp uses the body (forward, right, up) reference frame.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;position_body_sp**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-position">Position</Link></code>) <text>&#8212;</text> default all zeros idle setpoint

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;position_neu_sp**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-position">Position</Link></code>) <text>&#8212;</text> NEU (North, East, Up) position setpoint

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;global_sp**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-location">Location</Link></code>) <text>&#8212;</text> global setpoint

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;velocity_body_sp**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-velocity">Velocity</Link></code>) <text>&#8212;</text> body (forward, right, up) velocity setpoint

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;velocity_neu_sp**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-velocity">Velocity</Link></code>) <text>&#8212;</text> NEU (North, East, Up) velocity setpoint


---
## <><code class="docs-func">message</code></> PositionInfo


Information about the vehicle position.

Includes home position, global position (only valid with a GPS fix), relative position (only available on some vehicles), current velocity, and the current setpoint.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;home**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-location">Location</Link></code>) <text>&#8212;</text> global position that will be used when returning home

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;global_position**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-location">Location</Link></code>) <text>&#8212;</text> current global position of the vehicle

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;relative_position**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-position">Position</Link></code>) <text>&#8212;</text> current local position of the vehicle in the global NEU (North, East, Up) coordinate frame, relative to start position

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;velocity_neu**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-velocity">Velocity</Link></code>) <text>&#8212;</text> current velocity of the vehicle in the global NEU (North, East, Up) coordinate frame

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;velocity_body**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-velocity">Velocity</Link></code>) <text>&#8212;</text> current velocity of the vehicle in the body (forward, right, up) coordinate frame

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;setpoint_info**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-setpointinfo">SetpointInfo</Link></code>) <text>&#8212;</text> info on the current vehicle setpoint


---
## <><code class="docs-func">message</code></> GimbalStatus


Status of a gimbal.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;id**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> ID of the gimbal

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;pose_body**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-pose">Pose</Link></code>) <text>&#8212;</text> current pose in the body (forward, right, up) reference frame

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;pose_neu**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-pose">Pose</Link></code>) <text>&#8212;</text> current pose in the NEU (North, East, Up) reference frame


---
## <><code class="docs-func">message</code></> GimbalInfo


Info of all attached gimbals.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;num_gimbals**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> number of connected gimbals

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;gimbals**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-gimbalstatus">GimbalStatus</Link></code>) <text>&#8212;</text> list of connected gimbals


---
## <><code class="docs-func">message</code></> ImagingSensorStatus


Status of an imaging sensor.

Includes information about its type and resolution/stream settings.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;id**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> ID of the imaging sensor

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;type**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#enum-imagingsensortype">ImagingSensorType</Link></code>) <text>&#8212;</text> type of the imaging sensor

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;active**&nbsp;&nbsp;(`bool`) <text>&#8212;</text> indicates whether the imaging sensor is currently streaming

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;supports_secondary**&nbsp;&nbsp;(`bool`) <text>&#8212;</text> indicates whether the imaging sensor supports background streaming

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;current_fps**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> current streaming frames per second

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;max_fps**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> maximum streaming frames per second

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;h_res**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> horizontal resolution

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;v_res**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> vertical resolution

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;channels**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> number of image channels

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;h_fov**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> horizontal FOV

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;v_fov**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> vertical FOV

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;gimbal_mounted**&nbsp;&nbsp;(`bool`) <text>&#8212;</text> indicates if imaging sensor is gimbal mounted

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;gimbal_id**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> indicates which gimbal the imaging sensor is mounted on


---
## <><code class="docs-func">message</code></> ImagingSensorStreamStatus


Information about all imaging sensor streams.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;stream_capacity**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> the total number of allowed simultaneously streaming cameras

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;num_streams**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> the total number of currently streaming cameras

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;primary_cam**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> ID of the primary camera

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;secondary_cams**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> IDs of the secondary active cameras


---
## <><code class="docs-func">message</code></> ImagingSensorInfo


Information about all attached imaging sensors.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;stream_status**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-imagingsensorstreamstatus">ImagingSensorStreamStatus</Link></code>) <text>&#8212;</text> status of current imaging sensor streams

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;sensors**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-imagingsensorstatus">ImagingSensorStatus</Link></code>) <text>&#8212;</text> list of connected imaging sensors


---
## <><code class="docs-func">message</code></> AlertInfo


Information about all vehicle warning and alerts.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;battery_warning**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#enum-batterywarning">BatteryWarning</Link></code>) <text>&#8212;</text> battery warnings

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;gps_warning**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#enum-gpswarning">GPSWarning</Link></code>) <text>&#8212;</text> GPS warnings

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;magnetometer_warning**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#enum-magnetometerwarning">MagnetometerWarning</Link></code>) <text>&#8212;</text> magnetometer warnings

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;connection_warning**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#enum-connectionwarning">ConnectionWarning</Link></code>) <text>&#8212;</text> connection warnings

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;compass_warning**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#enum-compasswarning">CompassWarning</Link></code>) <text>&#8212;</text> compass warnings


---
## <><code class="docs-func">message</code></> DriverTelemetry


Telemetry message for the vehicle, originating from the driver module.

This message outlines all the current information about the vehicle. It
is one of three messages (`DriverTelemetry`, `Frame`, `MissionTelemetry`)
that is broadcast to attached compute services.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;timestamp**&nbsp;&nbsp;(<code>/google/protobuf/Timestamp</code>) <text>&#8212;</text> timestamp of message

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;telemetry_stream_info**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-telemetrystreaminfo">TelemetryStreamInfo</Link></code>) <text>&#8212;</text> info about current telemetry stream

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;vehicle_info**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-vehicleinfo">VehicleInfo</Link></code>) <text>&#8212;</text> the vehicle that this telemetry corresponds to

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;position_info**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-positioninfo">PositionInfo</Link></code>) <text>&#8212;</text> positional info about the vehicle

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;gimbal_info**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-gimbalinfo">GimbalInfo</Link></code>) <text>&#8212;</text> status on attached gimbals and their orientations

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;imaging_sensor_info**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-imagingsensorinfo">ImagingSensorInfo</Link></code>) <text>&#8212;</text> information about the vehicle imaging sensors

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;alert_info**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-alertinfo">AlertInfo</Link></code>) <text>&#8212;</text> enumeration of vehicle warnings


---
## <><code class="docs-func">message</code></> Frame


Imaging sensor frames, originating from the driver module.

This message provides frame data from currently streaming imaging sensors. It
is one of three messages (`DriverTelemetry`, `Frame`, `MissionTelemetry`)
that is broadcast to attached compute services.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;timestamp**&nbsp;&nbsp;(<code>/google/protobuf/Timestamp</code>) <text>&#8212;</text> capture timestamp of the frame

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;data**&nbsp;&nbsp;(`bytes`) <text>&#8212;</text> raw bytes representing the frame

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;h_res**&nbsp;&nbsp;(`uint64`) <text>&#8212;</text> horizontal frame resolution in pixels

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;v_res**&nbsp;&nbsp;(`uint64`) <text>&#8212;</text> vertical frame resolution in pixels

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;d_res**&nbsp;&nbsp;(`uint64`) <text>&#8212;</text> depth resolution in pixels

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;channels**&nbsp;&nbsp;(`uint64`) <text>&#8212;</text> number of channels

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;id**&nbsp;&nbsp;(`uint64`) <text>&#8212;</text> frame ID for future correlation

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;vehicle_info**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-vehicleinfo">VehicleInfo</Link></code>) <text>&#8212;</text> the vehicle that this telemetry corresponds to

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;position_info**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-positioninfo">PositionInfo</Link></code>) <text>&#8212;</text> positional info about the vehicle

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;gimbal_info**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-gimbalinfo">GimbalInfo</Link></code>) <text>&#8212;</text> status on attached gimbals and their orientations

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;imaging_sensor_info**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-imagingsensorinfo">ImagingSensorInfo</Link></code>) <text>&#8212;</text> information about the vehicle imaging sensors


---
## <><code class="docs-func">message</code></> MissionInfo


Information about the current mission.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;name**&nbsp;&nbsp;(`string`) <text>&#8212;</text> mission name

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;hash**&nbsp;&nbsp;(`int64`) <text>&#8212;</text> mission hash to establish version uniqueness

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;age**&nbsp;&nbsp;(<code>/google/protobuf/Timestamp</code>) <text>&#8212;</text> timestamp of upload

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;exec_state**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#enum-missionexecstate">MissionExecState</Link></code>) <text>&#8212;</text> execution state of the mission

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;task_state**&nbsp;&nbsp;(`string`) <text>&#8212;</text> task state of the mission (plaintext), if active


---
## <><code class="docs-func">message</code></> MissionTelemetry


Telemetry message for the mission, originating from the mission module.

This message outlines all current information about the mission. It
is one of three messages (`DriverTelemetry`, `Frame`, `MissionTelemetry`)
that is broadcast to attached compute services.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;timestamp**&nbsp;&nbsp;(<code>/google/protobuf/Timestamp</code>) <text>&#8212;</text> timestamp of message

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;telemetry_stream_info**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-telemetrystreaminfo">TelemetryStreamInfo</Link></code>) <text>&#8212;</text> info about the current telemetry stream

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;mission_info**&nbsp;&nbsp;(<code><Link to="/sdk/native/messages/telemetry#message-missioninfo">MissionInfo</Link></code>) <text>&#8212;</text> info about the current mission states


---
