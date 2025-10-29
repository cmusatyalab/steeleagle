---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# telemetry

---

## <><code class="docs-class">class</code></> MotionStatus

*Inherits from: <code>int</code>, <code>enum.Enum</code>*

Information about the motion of the vehicle.
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;MOTORS_OFF**&nbsp;&nbsp;(<code>0</code>) <text>&#8212;</text> motors of the vehicle are off

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;RAMPING_UP**&nbsp;&nbsp;(<code>1</code>) <text>&#8212;</text> motors of the vehicle are ramping

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;IDLE**&nbsp;&nbsp;(<code>2</code>) <text>&#8212;</text> the vehicle is on but idle

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;IN_TRANSIT**&nbsp;&nbsp;(<code>3</code>) <text>&#8212;</text> the vehicle is in motion

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;RAMPING_DOWN**&nbsp;&nbsp;(<code>4</code>) <text>&#8212;</text> motors of the vehicle are ramping down



<details>
<summary>View Source</summary>
```python
class MotionStatus(int, Enum):
    """Information about the motion of the vehicle.

    Attributes:
        MOTORS_OFF (0): motors of the vehicle are off
        RAMPING_UP (1): motors of the vehicle are ramping
        IDLE (2): the vehicle is on but idle
        IN_TRANSIT (3): the vehicle is in motion
        RAMPING_DOWN (4): motors of the vehicle are ramping down
    """
    MOTORS_OFF = 0 
    RAMPING_UP = 1 
    IDLE = 2 
    IN_TRANSIT = 3 
    RAMPING_DOWN = 4 

```
</details>


---
## <><code class="docs-class">class</code></> ImagingSensorType

*Inherits from: <code>int</code>, <code>enum.Enum</code>*

Imaging sensor types.
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;RGB**&nbsp;&nbsp;(<code>0</code>) <text>&#8212;</text> RGB camera

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;STEREO**&nbsp;&nbsp;(<code>1</code>) <text>&#8212;</text> stereo camera

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;THERMAL**&nbsp;&nbsp;(<code>2</code>) <text>&#8212;</text> thermal camera

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;NIGHT**&nbsp;&nbsp;(<code>3</code>) <text>&#8212;</text> night vision camera

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;LIDAR**&nbsp;&nbsp;(<code>4</code>) <text>&#8212;</text> LIDAR sensor

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;RGBD**&nbsp;&nbsp;(<code>5</code>) <text>&#8212;</text> RGB-Depth camera

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;TOF**&nbsp;&nbsp;(<code>6</code>) <text>&#8212;</text> ToF (time of flight) camera

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;RADAR**&nbsp;&nbsp;(<code>7</code>) <text>&#8212;</text> RADAR sensor



<details>
<summary>View Source</summary>
```python
class ImagingSensorType(int, Enum):
    """Imaging sensor types.

    Attributes:
        RGB (0): RGB camera
        STEREO (1): stereo camera
        THERMAL (2): thermal camera
        NIGHT (3): night vision camera
        LIDAR (4): LIDAR sensor
        RGBD (5): RGB-Depth camera
        TOF (6): ToF (time of flight) camera
        RADAR (7): RADAR sensor
    """
    RGB = 0 
    STEREO = 1 
    THERMAL = 2 
    NIGHT = 3 
    LIDAR = 4 
    RGBD = 5 
    TOF = 6 
    RADAR = 7 

```
</details>


---
## <><code class="docs-class">class</code></> BatteryWarning

*Inherits from: <code>int</code>, <code>enum.Enum</code>*

Battery warnings and alerts.
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;NONE**&nbsp;&nbsp;(<code>0</code>) <text>&#8212;</text> the vehicle is above 30% battery

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;LOW**&nbsp;&nbsp;(<code>1</code>) <text>&#8212;</text> the vehicle is below 30% battery

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;CRITICAL**&nbsp;&nbsp;(<code>2</code>) <text>&#8212;</text> the vehicle is below 15% battery



<details>
<summary>View Source</summary>
```python
class BatteryWarning(int, Enum):
    """Battery warnings and alerts.

    Attributes:
        NONE (0): the vehicle is above 30% battery
        LOW (1): the vehicle is below 30% battery
        CRITICAL (2): the vehicle is below 15% battery
    """
    NONE = 0 
    LOW = 1 
    CRITICAL = 2 

```
</details>


---
## <><code class="docs-class">class</code></> GPSWarning

*Inherits from: <code>int</code>, <code>enum.Enum</code>*

GPS fix warnings and alerts.
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;NO_GPS_WARNING**&nbsp;&nbsp;(<code>0</code>) <text>&#8212;</text> GPS readings are nominal and a fix has been achieved

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;WEAK_SIGNAL**&nbsp;&nbsp;(<code>1</code>) <text>&#8212;</text> weak GPS fix, expect errant global position data

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;NO_FIX**&nbsp;&nbsp;(<code>2</code>) <text>&#8212;</text> no GPS fix



<details>
<summary>View Source</summary>
```python
class GPSWarning(int, Enum):
    """GPS fix warnings and alerts.

    Attributes:
        NO_GPS_WARNING (0): GPS readings are nominal and a fix has been achieved
        WEAK_SIGNAL (1): weak GPS fix, expect errant global position data
        NO_FIX (2): no GPS fix
    """
    NO_GPS_WARNING = 0 
    WEAK_SIGNAL = 1 
    NO_FIX = 2 

```
</details>


---
## <><code class="docs-class">class</code></> MagnetometerWarning

*Inherits from: <code>int</code>, <code>enum.Enum</code>*

Magnetometer warnings and alerts.
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;NO_MAGNETOMETER_WARNING**&nbsp;&nbsp;(<code>0</code>) <text>&#8212;</text> magnetometer readings are nominal

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;PERTURBATION**&nbsp;&nbsp;(<code>1</code>) <text>&#8212;</text> the vehicle is experiencing magnetic perturbations



<details>
<summary>View Source</summary>
```python
class MagnetometerWarning(int, Enum):
    """Magnetometer warnings and alerts.

    Attributes:
        NO_MAGNETOMETER_WARNING (0): magnetometer readings are nominal
        PERTURBATION (1): the vehicle is experiencing magnetic perturbations
    """
    NO_MAGNETOMETER_WARNING = 0 
    PERTURBATION = 1 

```
</details>


---
## <><code class="docs-class">class</code></> ConnectionWarning

*Inherits from: <code>int</code>, <code>enum.Enum</code>*

Connection warnings and alerts.
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;NO_CONNECTION_WARNING**&nbsp;&nbsp;(<code>0</code>) <text>&#8212;</text> connection to remote server is nominal

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;DISCONNECTED**&nbsp;&nbsp;(<code>1</code>) <text>&#8212;</text> contact has been lost with the remote server

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;WEAK_CONNECTION**&nbsp;&nbsp;(<code>2</code>) <text>&#8212;</text> connection is experiencing interference or is weak



<details>
<summary>View Source</summary>
```python
class ConnectionWarning(int, Enum):
    """Connection warnings and alerts.

    Attributes:
        NO_CONNECTION_WARNING (0): connection to remote server is nominal
        DISCONNECTED (1): contact has been lost with the remote server
        WEAK_CONNECTION (2): connection is experiencing interference or is weak
    """
    NO_CONNECTION_WARNING = 0 
    DISCONNECTED = 1 
    WEAK_CONNECTION = 2 

```
</details>


---
## <><code class="docs-class">class</code></> CompassWarning

*Inherits from: <code>int</code>, <code>enum.Enum</code>*

Compass warnings and alerts.
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;NO_COMPASS_WARNING**&nbsp;&nbsp;(<code>0</code>) <text>&#8212;</text> absolute heading is nominal

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;WEAK_HEADING_LOCK**&nbsp;&nbsp;(<code>1</code>) <text>&#8212;</text> absolute heading is available but may be incorrect

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;NO_HEADING_LOCK**&nbsp;&nbsp;(<code>2</code>) <text>&#8212;</text> no absolute heading available from the vehicle



<details>
<summary>View Source</summary>
```python
class CompassWarning(int, Enum):
    """Compass warnings and alerts.

    Attributes:
        NO_COMPASS_WARNING (0): absolute heading is nominal
        WEAK_HEADING_LOCK (1): absolute heading is available but may be incorrect
        NO_HEADING_LOCK (2): no absolute heading available from the vehicle
    """
    NO_COMPASS_WARNING = 0 
    WEAK_HEADING_LOCK = 1 
    NO_HEADING_LOCK = 2 

```
</details>


---
## <><code class="docs-class">class</code></> MissionExecState

*Inherits from: <code>int</code>, <code>enum.Enum</code>*

Execution state of the current mission.
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;READY**&nbsp;&nbsp;(<code>0</code>) <text>&#8212;</text> mission is ready to be executed

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;IN_PROGRESS**&nbsp;&nbsp;(<code>1</code>) <text>&#8212;</text> mission is in progress

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;PAUSED**&nbsp;&nbsp;(<code>2</code>) <text>&#8212;</text> mission is paused

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;COMPLETED**&nbsp;&nbsp;(<code>3</code>) <text>&#8212;</text> mission has been completed

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;CANCELED**&nbsp;&nbsp;(<code>4</code>) <text>&#8212;</text> mission was cancelled



<details>
<summary>View Source</summary>
```python
class MissionExecState(int, Enum):
    """Execution state of the current mission.

    Attributes:
        READY (0): mission is ready to be executed
        IN_PROGRESS (1): mission is in progress
        PAUSED (2): mission is paused
        COMPLETED (3): mission has been completed
        CANCELED (4): mission was cancelled
    """
    READY = 0 
    IN_PROGRESS = 1 
    PAUSED = 2 
    COMPLETED = 3 
    CANCELED = 4 

```
</details>


---
## <><code class="docs-class">class</code></> TelemetryStreamInfo

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Information about the telemetry stream.    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;current_frequency**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> current frequency of telemetry messages [Hz]    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;max_frequency**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> maximum frequency of telemetry messages [Hz]    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;uptime**&nbsp;&nbsp;(<code>google.protobuf.duration_pb2.Duration</code>) <text>&#8212;</text> uptime of the stream



<details>
<summary>View Source</summary>
```python
@register_data
class TelemetryStreamInfo(Datatype):
    """Information about the telemetry stream.    
    
    Attributes:
        current_frequency (int): current frequency of telemetry messages [Hz]    
        max_frequency (int): maximum frequency of telemetry messages [Hz]    
        uptime (Duration): uptime of the stream    
    """
    current_frequency: int
    max_frequency: int
    uptime: Duration

```
</details>


---
## <><code class="docs-class">class</code></> BatteryInfo

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Information about the vehicle battery.    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;percentage**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> battery level [0-100]%



<details>
<summary>View Source</summary>
```python
@register_data
class BatteryInfo(Datatype):
    """Information about the vehicle battery.    
    
    Attributes:
        percentage (int): battery level [0-100]%    
    """
    percentage: int

```
</details>


---
## <><code class="docs-class">class</code></> GPSInfo

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Information about the vehicle GPS fix.    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;satellites**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> number of satellites used in GPS fix



<details>
<summary>View Source</summary>
```python
@register_data
class GPSInfo(Datatype):
    """Information about the vehicle GPS fix.    
    
    Attributes:
        satellites (int): number of satellites used in GPS fix    
    """
    satellites: int

```
</details>


---
## <><code class="docs-class">class</code></> CommsInfo

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Future: information about the vehicle's communication links.


<details>
<summary>View Source</summary>
```python
@register_data
class CommsInfo(Datatype):
    """Future: information about the vehicle's communication links.    
    """
    pass

```
</details>


---
## <><code class="docs-class">class</code></> VehicleInfo

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Information about the vehicle.

This includes the name, make, model and its current status (battery, GPS, comms, motion).    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;name**&nbsp;&nbsp;(<code>str</code>) <text>&#8212;</text> the vehicle that this telemetry corresponds to    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;model**&nbsp;&nbsp;(<code>str</code>) <text>&#8212;</text> model of the vehicle    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;manufacturer**&nbsp;&nbsp;(<code>str</code>) <text>&#8212;</text> manufacturer of the vehicle    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;motion_status**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-motionstatus">MotionStatus</Link></code>) <text>&#8212;</text> current status of the vehicle    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;battery_info**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-batteryinfo">BatteryInfo</Link></code>) <text>&#8212;</text> battery info for the vehicle    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;gps_info**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-gpsinfo">GPSInfo</Link></code>) <text>&#8212;</text> GPS sensor info for the vehicle    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;comms_info**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-commsinfo">CommsInfo</Link></code>) <text>&#8212;</text> communications info for the vehicle



<details>
<summary>View Source</summary>
```python
@register_data
class VehicleInfo(Datatype):
    """Information about the vehicle.

    This includes the name, make, model and its current status (battery, GPS, comms, motion).    
    
    Attributes:
        name (str): the vehicle that this telemetry corresponds to    
        model (str): model of the vehicle    
        manufacturer (str): manufacturer of the vehicle    
        motion_status (MotionStatus): current status of the vehicle    
        battery_info (BatteryInfo): battery info for the vehicle    
        gps_info (GPSInfo): GPS sensor info for the vehicle    
        comms_info (CommsInfo): communications info for the vehicle    
    """
    name: str
    model: str
    manufacturer: str
    motion_status: MotionStatus
    battery_info: BatteryInfo
    gps_info: GPSInfo
    comms_info: CommsInfo

```
</details>


---
## <><code class="docs-class">class</code></> SetpointInfo

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Information about the current setpoint.

Provides the current setpoint for the vehicle. A setpoint is a position or velocity target
that the vehicle is currently moving towards. By default, when the vehicle is idle, this
setpoint is a `position_body_sp` object set to all zeros. The frame of reference for each
setpoint is implied by the name; e.g. velocity_enu_sp uses the ENU (North, East, Up)
reference frame and velocity_body_sp uses the body (forward, right, up) reference frame.    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;position_body_sp**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/common#class-position">Position</Link></code>) <text>&#8212;</text> default all zeros idle setpoint    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;position_enu_sp**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/common#class-position">Position</Link></code>) <text>&#8212;</text> ENU (North, East, Up) position setpoint    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;global_sp**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/common#class-location">Location</Link></code>) <text>&#8212;</text> global setpoint    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;velocity_body_sp**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/common#class-velocity">Velocity</Link></code>) <text>&#8212;</text> body (forward, right, up) velocity setpoint    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;velocity_enu_sp**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/common#class-velocity">Velocity</Link></code>) <text>&#8212;</text> ENU (North, East, Up) velocity setpoint



<details>
<summary>View Source</summary>
```python
@register_data
class SetpointInfo(Datatype):
    """Information about the current setpoint.

    Provides the current setpoint for the vehicle. A setpoint is a position or velocity target
    that the vehicle is currently moving towards. By default, when the vehicle is idle, this
    setpoint is a `position_body_sp` object set to all zeros. The frame of reference for each
    setpoint is implied by the name; e.g. velocity_enu_sp uses the ENU (North, East, Up)
    reference frame and velocity_body_sp uses the body (forward, right, up) reference frame.    
    
    Attributes:
        position_body_sp (common.Position): default all zeros idle setpoint    
        position_enu_sp (common.Position): ENU (North, East, Up) position setpoint    
        global_sp (common.Location): global setpoint    
        velocity_body_sp (common.Velocity): body (forward, right, up) velocity setpoint    
        velocity_enu_sp (common.Velocity): ENU (North, East, Up) velocity setpoint    
    """
    position_body_sp: common.Position
    position_enu_sp: common.Position
    global_sp: common.Location
    velocity_body_sp: common.Velocity
    velocity_enu_sp: common.Velocity

```
</details>


---
## <><code class="docs-class">class</code></> PositionInfo

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Information about the vehicle position.

Includes home position, global position (only valid with a GPS fix), relative position (only available on some vehicles), current velocity, and the current setpoint.    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;home**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/common#class-location">Location</Link></code>) <text>&#8212;</text> global position that will be used when returning home    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;global_position**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/common#class-location">Location</Link></code>) <text>&#8212;</text> current global position of the vehicle    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;relative_position**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/common#class-position">Position</Link></code>) <text>&#8212;</text> current local position of the vehicle in the global ENU (North, East, Up) coordinate frame, relative to start position    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;velocity_enu**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/common#class-velocity">Velocity</Link></code>) <text>&#8212;</text> current velocity of the vehicle in the global ENU (North, East, Up) coordinate frame    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;velocity_body**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/common#class-velocity">Velocity</Link></code>) <text>&#8212;</text> current velocity of the vehicle in the body (forward, right, up)  coordinate frame    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;setpoint_info**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-setpointinfo">SetpointInfo</Link></code>) <text>&#8212;</text> info on the current vehicle setpoint



<details>
<summary>View Source</summary>
```python
@register_data
class PositionInfo(Datatype):
    """Information about the vehicle position.

    Includes home position, global position (only valid with a GPS fix), relative position (only available on some vehicles), current velocity, and the current setpoint.    
    
    Attributes:
        home (common.Location): global position that will be used when returning home    
        global_position (common.Location): current global position of the vehicle    
        relative_position (common.Position): current local position of the vehicle in the global ENU (North, East, Up) coordinate frame, relative to start position    
        velocity_enu (common.Velocity): current velocity of the vehicle in the global ENU (North, East, Up) coordinate frame    
        velocity_body (common.Velocity): current velocity of the vehicle in the body (forward, right, up)  coordinate frame    
        setpoint_info (SetpointInfo): info on the current vehicle setpoint    
    """
    home: common.Location
    global_position: common.Location
    relative_position: common.Position
    velocity_enu: common.Velocity
    velocity_body: common.Velocity
    setpoint_info: SetpointInfo

```
</details>


---
## <><code class="docs-class">class</code></> GimbalStatus

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Status of a gimbal.    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;id**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> ID of the gimbal    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;pose_body**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/common#class-pose">Pose</Link></code>) <text>&#8212;</text> current pose in the body (forward, right, up) reference frame    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;pose_enu**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/common#class-pose">Pose</Link></code>) <text>&#8212;</text> current pose in the ENU (North, East, Up) reference frame



<details>
<summary>View Source</summary>
```python
@register_data
class GimbalStatus(Datatype):
    """Status of a gimbal.    
    
    Attributes:
        id (int): ID of the gimbal    
        pose_body (common.Pose): current pose in the body (forward, right, up) reference frame    
        pose_enu (common.Pose): current pose in the ENU (North, East, Up) reference frame    
    """
    id: int
    pose_body: common.Pose
    pose_enu: common.Pose

```
</details>


---
## <><code class="docs-class">class</code></> GimbalInfo

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Info of all attached gimbals.    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;num_gimbals**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> number of connected gimbals    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;gimbals**&nbsp;&nbsp;(<code>List[<Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-gimbalstatus">GimbalStatus</Link>]</code>) <text>&#8212;</text> list of connected gimbals



<details>
<summary>View Source</summary>
```python
@register_data
class GimbalInfo(Datatype):
    """Info of all attached gimbals.    
    
    Attributes:
        num_gimbals (int): number of connected gimbals    
        gimbals (List[GimbalStatus]): list of connected gimbals    
    """
    num_gimbals: int
    gimbals: List[GimbalStatus]

```
</details>


---
## <><code class="docs-class">class</code></> ImagingSensorStatus

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Status of an imaging sensor.

Includes information about its type and resolution/stream settings.    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;id**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> ID of the imaging sensor    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;type**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-imagingsensortype">ImagingSensorType</Link></code>) <text>&#8212;</text> type of the imaging sensor    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;active**&nbsp;&nbsp;(<code>bool</code>) <text>&#8212;</text> indicates whether the imaging sensor is currently streaming    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;supports_secondary**&nbsp;&nbsp;(<code>bool</code>) <text>&#8212;</text> indicates whether the imaging sensor supports background streaming    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;current_fps**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> current streaming frames per second    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;max_fps**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> maximum streaming frames per second    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;h_res**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> horizontal resolution    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;v_res**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> vertical resolution    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;channels**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> number of image channels    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;h_fov**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> horizontal FOV    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;v_fov**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> vertical FOV    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;gimbal_mounted**&nbsp;&nbsp;(<code>bool</code>) <text>&#8212;</text> indicates if imaging sensor is gimbal mounted    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;gimbal_id**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> indicates which gimbal the imaging sensor is mounted on



<details>
<summary>View Source</summary>
```python
@register_data
class ImagingSensorStatus(Datatype):
    """Status of an imaging sensor.

    Includes information about its type and resolution/stream settings.    
    
    Attributes:
        id (int): ID of the imaging sensor    
        type (ImagingSensorType): type of the imaging sensor    
        active (bool): indicates whether the imaging sensor is currently streaming    
        supports_secondary (bool): indicates whether the imaging sensor supports background streaming    
        current_fps (int): current streaming frames per second    
        max_fps (int): maximum streaming frames per second    
        h_res (int): horizontal resolution    
        v_res (int): vertical resolution    
        channels (int): number of image channels    
        h_fov (int): horizontal FOV    
        v_fov (int): vertical FOV    
        gimbal_mounted (bool): indicates if imaging sensor is gimbal mounted    
        gimbal_id (int): indicates which gimbal the imaging sensor is mounted on    
    """
    id: int
    type: ImagingSensorType
    active: bool
    supports_secondary: bool
    current_fps: int
    max_fps: int
    h_res: int
    v_res: int
    channels: int
    h_fov: int
    v_fov: int
    gimbal_mounted: bool
    gimbal_id: int

```
</details>


---
## <><code class="docs-class">class</code></> ImagingSensorStreamStatus

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Information about all imaging sensor streams.    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;stream_capacity**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> the total number of allowed simultaneously streaming cameras    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;num_streams**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> the total number of currently streaming cameras    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;primary_cam**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> ID of the primary camera    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;secondary_cams**&nbsp;&nbsp;(<code>List[int]</code>) <text>&#8212;</text> IDs of the secondary active cameras



<details>
<summary>View Source</summary>
```python
@register_data
class ImagingSensorStreamStatus(Datatype):
    """Information about all imaging sensor streams.    
    
    Attributes:
        stream_capacity (int): the total number of allowed simultaneously streaming cameras    
        num_streams (int): the total number of currently streaming cameras    
        primary_cam (int): ID of the primary camera    
        secondary_cams (List[int]): IDs of the secondary active cameras    
    """
    stream_capacity: int
    num_streams: int
    primary_cam: int
    secondary_cams: List[int]

```
</details>


---
## <><code class="docs-class">class</code></> ImagingSensorInfo

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Information about all attached imaging sensors.    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;stream_status**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-imagingsensorstreamstatus">ImagingSensorStreamStatus</Link></code>) <text>&#8212;</text> status of current imaging sensor streams    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;sensors**&nbsp;&nbsp;(<code>List[<Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-imagingsensorstatus">ImagingSensorStatus</Link>]</code>) <text>&#8212;</text> list of connected imaging sensors



<details>
<summary>View Source</summary>
```python
@register_data
class ImagingSensorInfo(Datatype):
    """Information about all attached imaging sensors.    
    
    Attributes:
        stream_status (ImagingSensorStreamStatus): status of current imaging sensor streams    
        sensors (List[ImagingSensorStatus]): list of connected imaging sensors    
    """
    stream_status: ImagingSensorStreamStatus
    sensors: List[ImagingSensorStatus]

```
</details>


---
## <><code class="docs-class">class</code></> AlertInfo

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Information about all vehicle warning and alerts.    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;battery_warning**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-batterywarning">BatteryWarning</Link></code>) <text>&#8212;</text> battery warnings    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;gps_warning**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-gpswarning">GPSWarning</Link></code>) <text>&#8212;</text> GPS warnings    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;magnetometer_warning**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-magnetometerwarning">MagnetometerWarning</Link></code>) <text>&#8212;</text> magnetometer warnings    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;connection_warning**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-connectionwarning">ConnectionWarning</Link></code>) <text>&#8212;</text> connection warnings    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;compass_warning**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-compasswarning">CompassWarning</Link></code>) <text>&#8212;</text> compass warnings



<details>
<summary>View Source</summary>
```python
@register_data
class AlertInfo(Datatype):
    """Information about all vehicle warning and alerts.    
    
    Attributes:
        battery_warning (BatteryWarning): battery warnings    
        gps_warning (GPSWarning): GPS warnings    
        magnetometer_warning (MagnetometerWarning): magnetometer warnings    
        connection_warning (ConnectionWarning): connection warnings    
        compass_warning (CompassWarning): compass warnings    
    """
    battery_warning: BatteryWarning
    gps_warning: GPSWarning
    magnetometer_warning: MagnetometerWarning
    connection_warning: ConnectionWarning
    compass_warning: CompassWarning

```
</details>


---
## <><code class="docs-class">class</code></> DriverTelemetry

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Telemetry message for the vehicle, originating from the driver module.

This message outlines all the current information about the vehicle. It
is one of three messages (`DriverTelemetry`, `Frame`, `MissionTelemetry`)
that is broadcast to attached compute services.    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;timestamp**&nbsp;&nbsp;(<code>google.protobuf.timestamp_pb2.Timestamp</code>) <text>&#8212;</text> timestamp of message    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;telemetry_stream_info**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-telemetrystreaminfo">TelemetryStreamInfo</Link></code>) <text>&#8212;</text> info about current telemetry stream    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;vehicle_info**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-vehicleinfo">VehicleInfo</Link></code>) <text>&#8212;</text> the vehicle that this telemetry corresponds to    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;position_info**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-positioninfo">PositionInfo</Link></code>) <text>&#8212;</text> positional info about the vehicle    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;gimbal_info**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-gimbalinfo">GimbalInfo</Link></code>) <text>&#8212;</text> status on attached gimbals and their orientations    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;imaging_sensor_info**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-imagingsensorinfo">ImagingSensorInfo</Link></code>) <text>&#8212;</text> information about the vehicle imaging sensors    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;alert_info**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-alertinfo">AlertInfo</Link></code>) <text>&#8212;</text> enumeration of vehicle warnings



<details>
<summary>View Source</summary>
```python
@register_data
class DriverTelemetry(Datatype):
    """Telemetry message for the vehicle, originating from the driver module.

    This message outlines all the current information about the vehicle. It
    is one of three messages (`DriverTelemetry`, `Frame`, `MissionTelemetry`)
    that is broadcast to attached compute services.    
    
    Attributes:
        timestamp (Timestamp): timestamp of message    
        telemetry_stream_info (TelemetryStreamInfo): info about current telemetry stream    
        vehicle_info (VehicleInfo): the vehicle that this telemetry corresponds to    
        position_info (PositionInfo): positional info about the vehicle    
        gimbal_info (GimbalInfo): status on attached gimbals and their orientations    
        imaging_sensor_info (ImagingSensorInfo): information about the vehicle imaging sensors    
        alert_info (AlertInfo): enumeration of vehicle warnings    
    """
    timestamp: Timestamp
    telemetry_stream_info: TelemetryStreamInfo
    vehicle_info: VehicleInfo
    position_info: PositionInfo
    gimbal_info: GimbalInfo
    imaging_sensor_info: ImagingSensorInfo
    alert_info: AlertInfo

```
</details>


---
## <><code class="docs-class">class</code></> Frame

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Imaging sensor frames, originating from the driver module.

This message provides frame data from currently streaming imaging sensors. It
is one of three messages (`DriverTelemetry`, `Frame`, `MissionTelemetry`)
that is broadcast to attached compute services.    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;timestamp**&nbsp;&nbsp;(<code>google.protobuf.timestamp_pb2.Timestamp</code>) <text>&#8212;</text> capture timestamp of the frame    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;data**&nbsp;&nbsp;(<code>bytes</code>) <text>&#8212;</text> raw bytes representing the frame    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;h_res**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> horizontal frame resolution in pixels    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;v_res**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> vertical frame resolution in pixels    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;d_res**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> depth resolution in pixels    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;channels**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> number of channels    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;id**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> frame ID for future correlation



<details>
<summary>View Source</summary>
```python
@register_data
class Frame(Datatype):
    """Imaging sensor frames, originating from the driver module.

    This message provides frame data from currently streaming imaging sensors. It
    is one of three messages (`DriverTelemetry`, `Frame`, `MissionTelemetry`)
    that is broadcast to attached compute services.    
    
    Attributes:
        timestamp (Timestamp): capture timestamp of the frame    
        data (bytes): raw bytes representing the frame    
        h_res (int): horizontal frame resolution in pixels    
        v_res (int): vertical frame resolution in pixels    
        d_res (int): depth resolution in pixels    
        channels (int): number of channels    
        id (int): frame ID for future correlation    
    """
    timestamp: Timestamp
    data: bytes
    h_res: int
    v_res: int
    d_res: int
    channels: int
    id: int

```
</details>


---
## <><code class="docs-class">class</code></> MissionInfo

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Information about the current mission.    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;name**&nbsp;&nbsp;(<code>str</code>) <text>&#8212;</text> mission name    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;hash**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> mission hash to establish version uniqueness    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;age**&nbsp;&nbsp;(<code>google.protobuf.timestamp_pb2.Timestamp</code>) <text>&#8212;</text> timestamp of upload    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;exec_state**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-missionexecstate">MissionExecState</Link></code>) <text>&#8212;</text> execution state of the mission    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;task_state**&nbsp;&nbsp;(<code>str</code>) <text>&#8212;</text> task state of the mission (plaintext), if active



<details>
<summary>View Source</summary>
```python
@register_data
class MissionInfo(Datatype):
    """Information about the current mission.    
    
    Attributes:
        name (str): mission name    
        hash (int): mission hash to establish version uniqueness    
        age (Timestamp): timestamp of upload    
        exec_state (MissionExecState): execution state of the mission    
        task_state (str): task state of the mission (plaintext), if active    
    """
    name: str
    hash: int
    age: Timestamp
    exec_state: MissionExecState
    task_state: str

```
</details>


---
## <><code class="docs-class">class</code></> MissionTelemetry

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Telemetry message for the mission, originating from the mission module.

This message outlines all current information about the mission. It
is one of three messages (`DriverTelemetry`, `Frame`, `MissionTelemetry`)
that is broadcast to attached compute services.    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;timestamp**&nbsp;&nbsp;(<code>google.protobuf.timestamp_pb2.Timestamp</code>) <text>&#8212;</text> timestamp of message    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;telemetry_stream_info**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-telemetrystreaminfo">TelemetryStreamInfo</Link></code>) <text>&#8212;</text> info about the current telemetry stream    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;mission_info**&nbsp;&nbsp;(<code>List[<Link to="/sdk/python/steeleagle_sdk/api/datatypes/telemetry#class-missioninfo">MissionInfo</Link>]</code>) <text>&#8212;</text> info about the current mission states



<details>
<summary>View Source</summary>
```python
@register_data
class MissionTelemetry(Datatype):
    """Telemetry message for the mission, originating from the mission module.

    This message outlines all current information about the mission. It
    is one of three messages (`DriverTelemetry`, `Frame`, `MissionTelemetry`)
    that is broadcast to attached compute services.    
    
    Attributes:
        timestamp (Timestamp): timestamp of message    
        telemetry_stream_info (TelemetryStreamInfo): info about the current telemetry stream    
        mission_info (List[MissionInfo]): info about the current mission states    
    """
    timestamp: Timestamp
    telemetry_stream_info: TelemetryStreamInfo
    mission_info: List[MissionInfo]

```
</details>


---
