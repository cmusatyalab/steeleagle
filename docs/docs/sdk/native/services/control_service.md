---
toc_max_heading_level: 3
---

import Link from '@docusaurus/Link';

# control_service 
---
## <><code class="docs-class">service</code></> Control


Used for low-level control of a vehicle.

This service is hosted by the driver module and represents the global
control interface for the vehicle. Most methods called here will result
in actuation of the vehicle if it is armed (be careful!). Some methods,
like TakeOff, may take some time to complete. For this reason, it is
not advisable to set a timeout/deadline on the RPC call. However, to
ensure that the service is progressing, a client can either check
telemetry or listen for `IN_PROGRESS` response heartbeats which are
streamed back from the RPC while executing an operation.

### <><code class="docs-method">rpc</code></> Connect


Connect to the vehicle.

Connects to the underlying vehicle hardware. Generally, this 
method is called by the law authority on startup and is not
called by user code.

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-connectrequest">ConnectRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> Disconnect


Disconnect from the vehicle.

Disconnects from the underlying vehicle hardware. Generally,
this method is called by the law authority when it attempts
a driver restart and is not called by user code.

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-disconnectrequest">DisconnectRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> Arm


Order the vehicle to arm.

Arms the vehicle. This is required before any other commands
are run, otherwise the methods will return `FAILED_PRECONDITION`.
Once the vehicle is armed, all subsequent actuation methods
_will move the vehicle_. Make sure to go over the manufacturer
recommended vehicle-specific pre-operation checklist before arming.

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-armrequest">ArmRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> Disarm


Order the vehicle to disarm.

Disarms the vehicle. Prevents any further actuation methods
from executing, unless the vehicle is re-armed.

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-disarmrequest">DisarmRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> Joystick


Send a joystick command to the vehicle.

Causes the vehicle to accelerate towards a provided velocity
setpoint over a provided duration. This is useful for fine-grained 
control based on streamed datasink results or for tele-operating 
the vehicle from a remote commander.

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-joystickrequest">JoystickRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> TakeOff


Order the vehicle to take off.

Causes the vehicle to take off to a specified take off altitude.
If the vehicle is not a UAV, this method will be unimplemented.

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-takeoffrequest">TakeOffRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> Land


Order the vehicle to land.

Causes the vehicle to land at its current location. If the 
vehicle is not a UAV, this method will be unimplemented.

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-landrequest">LandRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> Hold


Order the vehicle to hold/loiter.

Causes the vehicle to hold at its current location and to
cancel any ongoing movement commands (`ReturnToHome` e.g.).

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-holdrequest">HoldRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> Kill


Orders an emergency shutdown of the vehicle motors.

Causes the vehicle to immediately turn off its motors. _If the 
vehicle is a UAV, this will result in a freefall_. Use this
method only in emergency situations.

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-killrequest">KillRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> SetHome


Set the home location of the vehicle.

Changes the home location of the vehicle. Future `ReturnToHome`
commands will move the vehicle to the provided location instead
of its starting position.

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-sethomerequest">SetHomeRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> ReturnToHome


Order the vehicle to return to its home position.

Causes the vehicle to return to its home position. If the home position 
has not been explicitly set, this will be its start position (defined 
as its takeoff position for UAVs). If the home position has been 
explicitly set, by `SetHome`, the vehicle will return to that 
position instead.

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-returntohomerequest">ReturnToHomeRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> SetGlobalPosition


Order the vehicle to move to a global position.

Causes the vehicle to transit to the provided global position. The vehicle
will interpret the heading of travel according to `heading_mode`:
- `TO_TARGET` -> turn to face the target position bearing
- `HEADING_START` -> turn to face the provided heading in the global position object. 

This will be the heading the vehicle maintains for the duration of transit. 
Generally only UAVs will support `HEADING_START`.

The vehicle will move towards the target at the specified maximum velocity 
until the vehicle has reached its destination. Error tolerance is determined 
by the driver. Maximum velocity is interpreted from `max_velocity` as follows:
- `x_vel` -> maximum _horizontal_ velocity
- `y_vel` -> ignored
- `z_vel` -> maximum _vertical_ velocity _(UAV only)_

If no maximum velocity is provided, the driver will use a preset speed usually 
determined by the manufacturer or hardware settings.

_(UAV only)_ During motion, the vehicle will also ascend or descend towards the 
target altitude, linearly interpolating this movement over the duration of
travel. The vehicle will interpret altitude from `altitude_mode` as follows:
- `ABSOLUTE` -> altitude is relative to MSL (Mean Sea Level)
- `RELATIVE` -> altitude is relative to take off position

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-setglobalpositionrequest">SetGlobalPositionRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> SetRelativePosition


Order the vehicle to move to a relative position.

Causes the vehicle to transit to the provided relative position. The vehicle
will interpret the input position according to `frame` as follows:
- `BODY` -> (`x`, `y`, `z`) = (forward offset, right offset, up offset) _from current position_
- `NEU` -> (`x`, `y`, `z`) = (north offset, east offset, up offset) _from start position_

The vehicle will move towards the target at the specified maximum velocity 
until the vehicle has reached its destination. Error tolerance is determined 
by the driver. Maximum velocity is interpreted from `max_velocity` as follows:
- `x_vel` -> maximum _horizontal_ velocity
- `y_vel` -> ignored
- `z_vel` -> maximum _vertical_ velocity _(UAV only)_

If no maximum velocity is provided, the driver will use a preset speed usually 
determined by the manufacturer or hardware settings.

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-setrelativepositionrequest">SetRelativePositionRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> SetVelocity


Order the vehicle to accelerate to a velocity.

Causes the vehicle to accelerate until it reaches a provided velocity.
Error tolerance is determined by the driver. The vehicle will interpret 
the input velocity according to `frame` as follows:
- `BODY` -> (`x_vel`, `y_vel`, `z_vel`) = (forward velocity, right velocity, up velocity)
- `NEU` -> (`x_vel`, `y_vel`, `z_vel`) = (north velocity, east velocity, up velocity)

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-setvelocityrequest">SetVelocityRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> SetHeading


Order the vehicle to set a new heading.

Causes the vehicle to turn to face the provided global position. The vehicle
will interpret the final heading according to `heading_mode`:
- `TO_TARGET` -> turn to face the target position bearing
- `HEADING_START` -> turn to face the provided heading in the global position object.

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-setheadingrequest">SetHeadingRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> SetGimbalPose


Order the vehicle to set the pose of a gimbal.

Causes the vehicle to actuate a gimbal to a new pose. The vehicle
will interpret the new pose type from `pose_mode` as follows: 
- `ABSOLUTE` -> absolute angle
- `RELATIVE` -> angle relative to current position
- `VELOCITY` -> angular velocities

The vehicle will interpret the new pose angles according to `frame` 
as follows:
- `BODY` -> (`pitch`, `roll`, `yaw`) = (body pitch, body roll, body yaw)
- `NEU` -> (`pitch`, `roll`, `yaw`) = (body pitch, body roll, global yaw)

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-setgimbalposerequest">SetGimbalPoseRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> ConfigureImagingSensorStream


Configure the vehicle imaging stream.

Sets which imaging sensors are streaming and sets their target
frame rates.

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-configureimagingsensorstreamrequest">ConfigureImagingSensorStreamRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> ConfigureTelemetryStream


Configure the vehicle telemetry stream.

Sets the frequency of the telemetry stream.

#### Accepts
<code><Link to="/sdk/native/services/control_service#message-configuretelemetrystreamrequest">ConfigureTelemetryStreamRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>


---

## <><code class="docs-func">enum</code></> AltitudeMode


Altitude mode switch.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;ABSOLUTE**&nbsp;&nbsp;(`0`) <text>&#8212;</text> meters above Mean Sea Level

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;RELATIVE**&nbsp;&nbsp;(`1`) <text>&#8212;</text> meters above takeoff position


---
## <><code class="docs-func">enum</code></> HeadingMode


Heading mode switch.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;TO_TARGET**&nbsp;&nbsp;(`0`) <text>&#8212;</text> orient towards the target location

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;HEADING_START**&nbsp;&nbsp;(`1`) <text>&#8212;</text> orient towards the given heading


---
## <><code class="docs-func">enum</code></> ReferenceFrame


Reference frame mode switch.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;BODY**&nbsp;&nbsp;(`0`) <text>&#8212;</text> vehicle reference frame

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;NEU**&nbsp;&nbsp;(`1`) <text>&#8212;</text> NEU (North, East, Up) reference frame


---
## <><code class="docs-func">enum</code></> PoseMode


Pose mode switch.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;ANGLE**&nbsp;&nbsp;(`0`) <text>&#8212;</text> absolute angle

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;OFFSET**&nbsp;&nbsp;(`1`) <text>&#8212;</text> request data // Offset from current

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;VELOCITY**&nbsp;&nbsp;(`2`) <text>&#8212;</text> rotational velocities


---
## <><code class="docs-func">message</code></> ConnectRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data


---
## <><code class="docs-func">message</code></> DisconnectRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data


---
## <><code class="docs-func">message</code></> ArmRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data


---
## <><code class="docs-func">message</code></> DisarmRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data


---
## <><code class="docs-func">message</code></> JoystickRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;velocity**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-velocity">Velocity</Link></code>) <text>&#8212;</text> target velocity to move towards

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;duration**&nbsp;&nbsp;(<code>/google/protobuf/Duration</code>) <text>&#8212;</text> time of actuation after which the vehicle will Hold


---
## <><code class="docs-func">message</code></> TakeOffRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;take_off_altitude**&nbsp;&nbsp;(`float`) <text>&#8212;</text> take off height in relative altitude [meters]


---
## <><code class="docs-func">message</code></> LandRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data


---
## <><code class="docs-func">message</code></> HoldRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data


---
## <><code class="docs-func">message</code></> KillRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data


---
## <><code class="docs-func">message</code></> SetHomeRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;location**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-location">Location</Link></code>) <text>&#8212;</text> new home location


---
## <><code class="docs-func">message</code></> ReturnToHomeRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data


---
## <><code class="docs-func">message</code></> SetGlobalPositionRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;location**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-location">Location</Link></code>) <text>&#8212;</text> target global position

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;heading_mode**&nbsp;&nbsp;(<code><Link to="/sdk/native/services/control_service#enum-headingmode">HeadingMode</Link></code>) <text>&#8212;</text> determines how the vehicle will orient during transit (default: `TO_TARGET`)

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;altitude_mode**&nbsp;&nbsp;(<code><Link to="/sdk/native/services/control_service#enum-altitudemode">AltitudeMode</Link></code>) <text>&#8212;</text> determines how the vehicle will interpret altitude (default: `ABSOLUTE`)

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;max_velocity**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-velocity">Velocity</Link></code>) <text>&#8212;</text> maximum velocity during transit


---
## <><code class="docs-func">message</code></> SetRelativePositionRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;position**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-position">Position</Link></code>) <text>&#8212;</text> target relative position

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;max_velocity**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-velocity">Velocity</Link></code>) <text>&#8212;</text> maximum velocity during transit

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;frame**&nbsp;&nbsp;(<code><Link to="/sdk/native/services/control_service#enum-referenceframe">ReferenceFrame</Link></code>) <text>&#8212;</text> frame of reference


---
## <><code class="docs-func">message</code></> SetVelocityRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;velocity**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-velocity">Velocity</Link></code>) <text>&#8212;</text> target velocity

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;frame**&nbsp;&nbsp;(<code><Link to="/sdk/native/services/control_service#enum-referenceframe">ReferenceFrame</Link></code>) <text>&#8212;</text> frame of reference


---
## <><code class="docs-func">message</code></> SetHeadingRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;location**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-location">Location</Link></code>) <text>&#8212;</text> target heading or global location to look at

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;heading_mode**&nbsp;&nbsp;(<code><Link to="/sdk/native/services/control_service#enum-headingmode">HeadingMode</Link></code>) <text>&#8212;</text> determines how the drone will orient


---
## <><code class="docs-func">message</code></> SetGimbalPoseRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;gimbal_id**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> ID of the target gimbal

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;pose**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-pose">Pose</Link></code>) <text>&#8212;</text> target pose

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;pose_mode**&nbsp;&nbsp;(<code><Link to="/sdk/native/services/control_service#enum-posemode">PoseMode</Link></code>) <text>&#8212;</text> specifies how to interpret the target pose

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;frame**&nbsp;&nbsp;(<code><Link to="/sdk/native/services/control_service#enum-referenceframe">ReferenceFrame</Link></code>) <text>&#8212;</text> frame of reference


---
## <><code class="docs-func">message</code></> ImagingSensorConfiguration


Configuration for an imaging sensor.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;id**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> target imaging sensor ID

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;set_primary**&nbsp;&nbsp;(`bool`) <text>&#8212;</text> set this sensor as the primary stream

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;set_fps**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> target FPS for stream


---
## <><code class="docs-func">message</code></> ConfigureImagingSensorStreamRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;configurations**&nbsp;&nbsp;(<code><Link to="/sdk/native/services/control_service#message-imagingsensorconfiguration">ImagingSensorConfiguration</Link></code>) <text>&#8212;</text> list of configurations to be updated


---
## <><code class="docs-func">message</code></> ConfigureTelemetryStreamRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;frequency**&nbsp;&nbsp;(`uint32`) <text>&#8212;</text> target frequency of telemetry generation, in Hz


---
