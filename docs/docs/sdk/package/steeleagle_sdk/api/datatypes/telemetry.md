---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';

# telemetry

---

## <><code style={{color: '#b52ee6'}}>class</code></> MotionStatus


Information about the motion of the vehicle.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> MOTORS_OFF** (<code>0</code>) <text>&#8212;</text> motors of the vehicle are off

**<><code style={{color: '#e0a910'}}>attr</code></> RAMPING_UP** (<code>1</code>) <text>&#8212;</text> motors of the vehicle are ramping

**<><code style={{color: '#e0a910'}}>attr</code></> IDLE** (<code>2</code>) <text>&#8212;</text> the vehicle is on but idle

**<><code style={{color: '#e0a910'}}>attr</code></> IN_TRANSIT** (<code>3</code>) <text>&#8212;</text> the vehicle is in motion

**<><code style={{color: '#e0a910'}}>attr</code></> RAMPING_DOWN** (<code>4</code>) <text>&#8212;</text> motors of the vehicle are ramping down



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
## <><code style={{color: '#b52ee6'}}>class</code></> ImagingSensorType


Imaging sensor types.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> RGB** (<code>0</code>) <text>&#8212;</text> RGB camera

**<><code style={{color: '#e0a910'}}>attr</code></> STEREO** (<code>1</code>) <text>&#8212;</text> stereo camera

**<><code style={{color: '#e0a910'}}>attr</code></> THERMAL** (<code>2</code>) <text>&#8212;</text> thermal camera

**<><code style={{color: '#e0a910'}}>attr</code></> NIGHT** (<code>3</code>) <text>&#8212;</text> night vision camera

**<><code style={{color: '#e0a910'}}>attr</code></> LIDAR** (<code>4</code>) <text>&#8212;</text> LIDAR sensor

**<><code style={{color: '#e0a910'}}>attr</code></> RGBD** (<code>5</code>) <text>&#8212;</text> RGB-Depth camera

**<><code style={{color: '#e0a910'}}>attr</code></> TOF** (<code>6</code>) <text>&#8212;</text> ToF (time of flight) camera

**<><code style={{color: '#e0a910'}}>attr</code></> RADAR** (<code>7</code>) <text>&#8212;</text> RADAR sensor



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
## <><code style={{color: '#b52ee6'}}>class</code></> BatteryWarning


Battery warnings and alerts.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> NONE** (<code>0</code>) <text>&#8212;</text> the vehicle is above 30% battery

**<><code style={{color: '#e0a910'}}>attr</code></> LOW** (<code>1</code>) <text>&#8212;</text> the vehicle is below 30% battery

**<><code style={{color: '#e0a910'}}>attr</code></> CRITICAL** (<code>2</code>) <text>&#8212;</text> the vehicle is below 15% battery



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
## <><code style={{color: '#b52ee6'}}>class</code></> GPSWarning


GPS fix warnings and alerts.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> NO_GPS_WARNING** (<code>0</code>) <text>&#8212;</text> GPS readings are nominal and a fix has been achieved

**<><code style={{color: '#e0a910'}}>attr</code></> WEAK_SIGNAL** (<code>1</code>) <text>&#8212;</text> weak GPS fix, expect errant global position data

**<><code style={{color: '#e0a910'}}>attr</code></> NO_FIX** (<code>2</code>) <text>&#8212;</text> no GPS fix



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
## <><code style={{color: '#b52ee6'}}>class</code></> MagnetometerWarning


Magnetometer warnings and alerts.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> NO_MAGNETOMETER_WARNING** (<code>0</code>) <text>&#8212;</text> magnetometer readings are nominal

**<><code style={{color: '#e0a910'}}>attr</code></> PERTURBATION** (<code>1</code>) <text>&#8212;</text> the vehicle is experiencing magnetic perturbations



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
## <><code style={{color: '#b52ee6'}}>class</code></> ConnectionWarning


Connection warnings and alerts.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> NO_CONNECTION_WARNING** (<code>0</code>) <text>&#8212;</text> connection to remote server is nominal

**<><code style={{color: '#e0a910'}}>attr</code></> DISCONNECTED** (<code>1</code>) <text>&#8212;</text> contact has been lost with the remote server

**<><code style={{color: '#e0a910'}}>attr</code></> WEAK_CONNECTION** (<code>2</code>) <text>&#8212;</text> connection is experiencing interference or is weak



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
## <><code style={{color: '#b52ee6'}}>class</code></> CompassWarning


Compass warnings and alerts.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> NO_COMPASS_WARNING** (<code>0</code>) <text>&#8212;</text> absolute heading is nominal

**<><code style={{color: '#e0a910'}}>attr</code></> WEAK_HEADING_LOCK** (<code>1</code>) <text>&#8212;</text> absolute heading is available but may be incorrect

**<><code style={{color: '#e0a910'}}>attr</code></> NO_HEADING_LOCK** (<code>2</code>) <text>&#8212;</text> no absolute heading available from the vehicle



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
## <><code style={{color: '#b52ee6'}}>class</code></> MissionExecState


Execution state of the current mission.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> READY** (<code>0</code>) <text>&#8212;</text> mission is ready to be executed

**<><code style={{color: '#e0a910'}}>attr</code></> IN_PROGRESS** (<code>1</code>) <text>&#8212;</text> mission is in progress

**<><code style={{color: '#e0a910'}}>attr</code></> PAUSED** (<code>2</code>) <text>&#8212;</text> mission is paused

**<><code style={{color: '#e0a910'}}>attr</code></> COMPLETED** (<code>3</code>) <text>&#8212;</text> mission has been completed

**<><code style={{color: '#e0a910'}}>attr</code></> CANCELED** (<code>4</code>) <text>&#8212;</text> mission was cancelled



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
## <><code style={{color: '#b52ee6'}}>class</code></> TelemetryStreamInfo


Information about the telemetry stream.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> current_frequency** (<code>int</code>) <text>&#8212;</text> current frequency of telemetry messages [Hz]    

**<><code style={{color: '#e0a910'}}>attr</code></> max_frequency** (<code>int</code>) <text>&#8212;</text> maximum frequency of telemetry messages [Hz]    

**<><code style={{color: '#e0a910'}}>attr</code></> uptime** (<code>google.protobuf.duration_pb2.Duration</code>) <text>&#8212;</text> uptime of the stream



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
## <><code style={{color: '#b52ee6'}}>class</code></> BatteryInfo


Information about the vehicle battery.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> percentage** (<code>int</code>) <text>&#8212;</text> battery level [0-100]%



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
## <><code style={{color: '#b52ee6'}}>class</code></> GPSInfo


Information about the vehicle GPS fix.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> satellites** (<code>int</code>) <text>&#8212;</text> number of satellites used in GPS fix



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
## <><code style={{color: '#b52ee6'}}>class</code></> CommsInfo


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
## <><code style={{color: '#b52ee6'}}>class</code></> VehicleInfo


Information about the vehicle.

This includes the name, make, model and its current status (battery, GPS, comms, motion).    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> name** (<code>str</code>) <text>&#8212;</text> the vehicle that this telemetry corresponds to    

**<><code style={{color: '#e0a910'}}>attr</code></> model** (<code>str</code>) <text>&#8212;</text> model of the vehicle    

**<><code style={{color: '#e0a910'}}>attr</code></> manufacturer** (<code>str</code>) <text>&#8212;</text> manufacturer of the vehicle    

**<><code style={{color: '#e0a910'}}>attr</code></> motion_status** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-motionstatus">MotionStatus</Link></code>) <text>&#8212;</text> current status of the vehicle    

**<><code style={{color: '#e0a910'}}>attr</code></> battery_info** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-batteryinfo">BatteryInfo</Link></code>) <text>&#8212;</text> battery info for the vehicle    

**<><code style={{color: '#e0a910'}}>attr</code></> gps_info** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-gpsinfo">GPSInfo</Link></code>) <text>&#8212;</text> GPS sensor info for the vehicle    

**<><code style={{color: '#e0a910'}}>attr</code></> comms_info** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-commsinfo">CommsInfo</Link></code>) <text>&#8212;</text> communications info for the vehicle



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
## <><code style={{color: '#b52ee6'}}>class</code></> SetpointInfo


Information about the current setpoint.

Provides the current setpoint for the vehicle. A setpoint is a position or velocity target
that the vehicle is currently moving towards. By default, when the vehicle is idle, this
setpoint is a `position_body_sp` object set to all zeros. The frame of reference for each
setpoint is implied by the name; e.g. velocity_enu_sp uses the ENU (North, East, Up)
reference frame and velocity_body_sp uses the body (forward, right, up) reference frame.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> position_body_sp** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/common#class-position">Position</Link></code>) <text>&#8212;</text> default all zeros idle setpoint    

**<><code style={{color: '#e0a910'}}>attr</code></> position_enu_sp** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/common#class-position">Position</Link></code>) <text>&#8212;</text> ENU (North, East, Up) position setpoint    

**<><code style={{color: '#e0a910'}}>attr</code></> global_sp** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/common#class-location">Location</Link></code>) <text>&#8212;</text> global setpoint    

**<><code style={{color: '#e0a910'}}>attr</code></> velocity_body_sp** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/common#class-velocity">Velocity</Link></code>) <text>&#8212;</text> body (forward, right, up) velocity setpoint    

**<><code style={{color: '#e0a910'}}>attr</code></> velocity_enu_sp** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/common#class-velocity">Velocity</Link></code>) <text>&#8212;</text> ENU (North, East, Up) velocity setpoint



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
## <><code style={{color: '#b52ee6'}}>class</code></> PositionInfo


Information about the vehicle position.

Includes home position, global position (only valid with a GPS fix), relative position (only available on some vehicles), current velocity, and the current setpoint.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> home** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/common#class-location">Location</Link></code>) <text>&#8212;</text> global position that will be used when returning home    

**<><code style={{color: '#e0a910'}}>attr</code></> global_position** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/common#class-location">Location</Link></code>) <text>&#8212;</text> current global position of the vehicle    

**<><code style={{color: '#e0a910'}}>attr</code></> relative_position** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/common#class-position">Position</Link></code>) <text>&#8212;</text> current local position of the vehicle in the global ENU (North, East, Up) coordinate frame, relative to start position    

**<><code style={{color: '#e0a910'}}>attr</code></> velocity_enu** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/common#class-velocity">Velocity</Link></code>) <text>&#8212;</text> current velocity of the vehicle in the global ENU (North, East, Up) coordinate frame    

**<><code style={{color: '#e0a910'}}>attr</code></> velocity_body** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/common#class-velocity">Velocity</Link></code>) <text>&#8212;</text> current velocity of the vehicle in the body (forward, right, up)  coordinate frame    

**<><code style={{color: '#e0a910'}}>attr</code></> setpoint_info** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-setpointinfo">SetpointInfo</Link></code>) <text>&#8212;</text> info on the current vehicle setpoint



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
## <><code style={{color: '#b52ee6'}}>class</code></> GimbalStatus


Status of a gimbal.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> id** (<code>int</code>) <text>&#8212;</text> ID of the gimbal    

**<><code style={{color: '#e0a910'}}>attr</code></> pose_body** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/common#class-pose">Pose</Link></code>) <text>&#8212;</text> current pose in the body (forward, right, up) reference frame    

**<><code style={{color: '#e0a910'}}>attr</code></> pose_enu** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/common#class-pose">Pose</Link></code>) <text>&#8212;</text> current pose in the ENU (North, East, Up) reference frame



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
## <><code style={{color: '#b52ee6'}}>class</code></> GimbalInfo


Info of all attached gimbals.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> num_gimbals** (<code>int</code>) <text>&#8212;</text> number of connected gimbals    

**<><code style={{color: '#e0a910'}}>attr</code></> gimbals** (<code>List[<Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-gimbalstatus">GimbalStatus</Link>]</code>) <text>&#8212;</text> list of connected gimbals



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
## <><code style={{color: '#b52ee6'}}>class</code></> ImagingSensorStatus


Status of an imaging sensor.

Includes information about its type and resolution/stream settings.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> id** (<code>int</code>) <text>&#8212;</text> ID of the imaging sensor    

**<><code style={{color: '#e0a910'}}>attr</code></> type** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-imagingsensortype">ImagingSensorType</Link></code>) <text>&#8212;</text> type of the imaging sensor    

**<><code style={{color: '#e0a910'}}>attr</code></> active** (<code>bool</code>) <text>&#8212;</text> indicates whether the imaging sensor is currently streaming    

**<><code style={{color: '#e0a910'}}>attr</code></> supports_secondary** (<code>bool</code>) <text>&#8212;</text> indicates whether the imaging sensor supports background streaming    

**<><code style={{color: '#e0a910'}}>attr</code></> current_fps** (<code>int</code>) <text>&#8212;</text> current streaming frames per second    

**<><code style={{color: '#e0a910'}}>attr</code></> max_fps** (<code>int</code>) <text>&#8212;</text> maximum streaming frames per second    

**<><code style={{color: '#e0a910'}}>attr</code></> h_res** (<code>int</code>) <text>&#8212;</text> horizontal resolution    

**<><code style={{color: '#e0a910'}}>attr</code></> v_res** (<code>int</code>) <text>&#8212;</text> vertical resolution    

**<><code style={{color: '#e0a910'}}>attr</code></> channels** (<code>int</code>) <text>&#8212;</text> number of image channels    

**<><code style={{color: '#e0a910'}}>attr</code></> h_fov** (<code>int</code>) <text>&#8212;</text> horizontal FOV    

**<><code style={{color: '#e0a910'}}>attr</code></> v_fov** (<code>int</code>) <text>&#8212;</text> vertical FOV    

**<><code style={{color: '#e0a910'}}>attr</code></> gimbal_mounted** (<code>bool</code>) <text>&#8212;</text> indicates if imaging sensor is gimbal mounted    

**<><code style={{color: '#e0a910'}}>attr</code></> gimbal_id** (<code>int</code>) <text>&#8212;</text> indicates which gimbal the imaging sensor is mounted on



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
## <><code style={{color: '#b52ee6'}}>class</code></> ImagingSensorStreamStatus


Information about all imaging sensor streams.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> stream_capacity** (<code>int</code>) <text>&#8212;</text> the total number of allowed simultaneously streaming cameras    

**<><code style={{color: '#e0a910'}}>attr</code></> num_streams** (<code>int</code>) <text>&#8212;</text> the total number of currently streaming cameras    

**<><code style={{color: '#e0a910'}}>attr</code></> primary_cam** (<code>int</code>) <text>&#8212;</text> ID of the primary camera    

**<><code style={{color: '#e0a910'}}>attr</code></> secondary_cams** (<code>List[int]</code>) <text>&#8212;</text> IDs of the secondary active cameras



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
## <><code style={{color: '#b52ee6'}}>class</code></> ImagingSensorInfo


Information about all attached imaging sensors.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> stream_status** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-imagingsensorstreamstatus">ImagingSensorStreamStatus</Link></code>) <text>&#8212;</text> status of current imaging sensor streams    

**<><code style={{color: '#e0a910'}}>attr</code></> sensors** (<code>List[<Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-imagingsensorstatus">ImagingSensorStatus</Link>]</code>) <text>&#8212;</text> list of connected imaging sensors



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
## <><code style={{color: '#b52ee6'}}>class</code></> AlertInfo


Information about all vehicle warning and alerts.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> battery_warning** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-batterywarning">BatteryWarning</Link></code>) <text>&#8212;</text> battery warnings    

**<><code style={{color: '#e0a910'}}>attr</code></> gps_warning** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-gpswarning">GPSWarning</Link></code>) <text>&#8212;</text> GPS warnings    

**<><code style={{color: '#e0a910'}}>attr</code></> magnetometer_warning** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-magnetometerwarning">MagnetometerWarning</Link></code>) <text>&#8212;</text> magnetometer warnings    

**<><code style={{color: '#e0a910'}}>attr</code></> connection_warning** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-connectionwarning">ConnectionWarning</Link></code>) <text>&#8212;</text> connection warnings    

**<><code style={{color: '#e0a910'}}>attr</code></> compass_warning** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-compasswarning">CompassWarning</Link></code>) <text>&#8212;</text> compass warnings



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
## <><code style={{color: '#b52ee6'}}>class</code></> DriverTelemetry


Telemetry message for the vehicle, originating from the driver module.

This message outlines all the current information about the vehicle. It
is one of three messages (`DriverTelemetry`, `Frame`, `MissionTelemetry`)
that is broadcast to attached compute services.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> timestamp** (<code>google.protobuf.timestamp_pb2.Timestamp</code>) <text>&#8212;</text> timestamp of message    

**<><code style={{color: '#e0a910'}}>attr</code></> telemetry_stream_info** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-telemetrystreaminfo">TelemetryStreamInfo</Link></code>) <text>&#8212;</text> info about current telemetry stream    

**<><code style={{color: '#e0a910'}}>attr</code></> vehicle_info** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-vehicleinfo">VehicleInfo</Link></code>) <text>&#8212;</text> the vehicle that this telemetry corresponds to    

**<><code style={{color: '#e0a910'}}>attr</code></> position_info** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-positioninfo">PositionInfo</Link></code>) <text>&#8212;</text> positional info about the vehicle    

**<><code style={{color: '#e0a910'}}>attr</code></> gimbal_info** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-gimbalinfo">GimbalInfo</Link></code>) <text>&#8212;</text> status on attached gimbals and their orientations    

**<><code style={{color: '#e0a910'}}>attr</code></> imaging_sensor_info** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-imagingsensorinfo">ImagingSensorInfo</Link></code>) <text>&#8212;</text> information about the vehicle imaging sensors    

**<><code style={{color: '#e0a910'}}>attr</code></> alert_info** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-alertinfo">AlertInfo</Link></code>) <text>&#8212;</text> enumeration of vehicle warnings



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
## <><code style={{color: '#b52ee6'}}>class</code></> Frame


Imaging sensor frames, originating from the driver module.

This message provides frame data from currently streaming imaging sensors. It
is one of three messages (`DriverTelemetry`, `Frame`, `MissionTelemetry`)
that is broadcast to attached compute services.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> timestamp** (<code>google.protobuf.timestamp_pb2.Timestamp</code>) <text>&#8212;</text> capture timestamp of the frame    

**<><code style={{color: '#e0a910'}}>attr</code></> data** (<code>bytes</code>) <text>&#8212;</text> raw bytes representing the frame    

**<><code style={{color: '#e0a910'}}>attr</code></> h_res** (<code>int</code>) <text>&#8212;</text> horizontal frame resolution in pixels    

**<><code style={{color: '#e0a910'}}>attr</code></> v_res** (<code>int</code>) <text>&#8212;</text> vertical frame resolution in pixels    

**<><code style={{color: '#e0a910'}}>attr</code></> d_res** (<code>int</code>) <text>&#8212;</text> depth resolution in pixels    

**<><code style={{color: '#e0a910'}}>attr</code></> channels** (<code>int</code>) <text>&#8212;</text> number of channels    

**<><code style={{color: '#e0a910'}}>attr</code></> id** (<code>int</code>) <text>&#8212;</text> frame ID for future correlation



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
## <><code style={{color: '#b52ee6'}}>class</code></> MissionInfo


Information about the current mission.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> name** (<code>str</code>) <text>&#8212;</text> mission name    

**<><code style={{color: '#e0a910'}}>attr</code></> hash** (<code>int</code>) <text>&#8212;</text> mission hash to establish version uniqueness    

**<><code style={{color: '#e0a910'}}>attr</code></> age** (<code>google.protobuf.timestamp_pb2.Timestamp</code>) <text>&#8212;</text> timestamp of upload    

**<><code style={{color: '#e0a910'}}>attr</code></> exec_state** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-missionexecstate">MissionExecState</Link></code>) <text>&#8212;</text> execution state of the mission    

**<><code style={{color: '#e0a910'}}>attr</code></> task_state** (<code>str</code>) <text>&#8212;</text> task state of the mission (plaintext), if active



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
## <><code style={{color: '#b52ee6'}}>class</code></> MissionTelemetry


Telemetry message for the mission, originating from the mission module.

This message outlines all current information about the mission. It
is one of three messages (`DriverTelemetry`, `Frame`, `MissionTelemetry`)
that is broadcast to attached compute services.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> timestamp** (<code>google.protobuf.timestamp_pb2.Timestamp</code>) <text>&#8212;</text> timestamp of message    

**<><code style={{color: '#e0a910'}}>attr</code></> telemetry_stream_info** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-telemetrystreaminfo">TelemetryStreamInfo</Link></code>) <text>&#8212;</text> info about the current telemetry stream    

**<><code style={{color: '#e0a910'}}>attr</code></> mission_info** (<code>List[<Link to="/sdk/package/steeleagle_sdk/api/datatypes/telemetry#class-missioninfo">MissionInfo</Link>]</code>) <text>&#8212;</text> info about the current mission states



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
