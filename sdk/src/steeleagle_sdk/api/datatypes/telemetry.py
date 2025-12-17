from typing import List, Optional

from pydantic import Field
from .timestamp import Timestamp
from .duration import Duration
from enum import Enum
from ._base import Datatype
from . import common


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


class MagnetometerWarning(int, Enum):
    """Magnetometer warnings and alerts.

    Attributes:
        NO_MAGNETOMETER_WARNING (0): magnetometer readings are nominal
        PERTURBATION (1): the vehicle is experiencing magnetic perturbations
    """

    NO_MAGNETOMETER_WARNING = 0
    PERTURBATION = 1


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


class TelemetryStreamInfo(Datatype):
    """Information about the telemetry stream.

    Attributes:
        current_frequency (int): current frequency of telemetry messages [Hz]
        max_frequency (int): maximum frequency of telemetry messages [Hz]
        uptime (Duration): uptime of the stream
    """

    current_frequency: Optional[int] = None
    max_frequency: Optional[int] = None
    uptime: Optional[Duration] = None


class BatteryInfo(Datatype):
    """Information about the vehicle battery.

    Attributes:
        percentage (int): battery level [0-100]%
    """

    percentage: Optional[int] = None


class GPSInfo(Datatype):
    """Information about the vehicle GPS fix.

    Attributes:
        satellites (int): number of satellites used in GPS fix
    """

    satellites: Optional[int] = None


class CommsInfo(Datatype):
    """Future: information about the vehicle's communication links."""

    pass


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

    name: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    motion_status: Optional[MotionStatus] = None
    battery_info: Optional[BatteryInfo] = None
    gps_info: Optional[GPSInfo] = None
    comms_info: Optional[CommsInfo] = None


class SetpointInfo(Datatype):
    """Information about the current setpoint.

    Provides the current setpoint for the vehicle. A setpoint is a position or velocity target
    that the vehicle is currently moving towards. By default, when the vehicle is idle, this
    setpoint is a `position_body_sp` object set to all zeros. The frame of reference for each
    setpoint is implied by the name; e.g. velocity_neu_sp uses the NEU (North, East, Up)
    reference frame and velocity_body_sp uses the body (forward, right, up) reference frame.

    Attributes:
        position_body_sp (common.Position): default all zeros idle setpoint
        position_neu_sp (common.Position): NEU (North, East, Up) position setpoint
        global_sp (common.Location): global setpoint
        velocity_body_sp (common.Velocity): body (forward, right, up) velocity setpoint
        velocity_neu_sp (common.Velocity): NEU (North, East, Up) velocity setpoint
    """

    position_body_sp: Optional[common.Position] = None
    position_neu_sp: Optional[common.Position] = None
    global_sp: Optional[common.Location] = None
    velocity_body_sp: Optional[common.Velocity] = None
    velocity_neu_sp: Optional[common.Velocity] = None


class PositionInfo(Datatype):
    """Information about the vehicle position.

    Includes home position, global position (only valid with a GPS fix), relative position (only available on some vehicles), current velocity, and the current setpoint.

    Attributes:
        home (common.Location): global position that will be used when returning home
        global_position (common.Location): current global position of the vehicle
        relative_position (common.Position): current local position of the vehicle in the global NEU (North, East, Up) coordinate frame, relative to start position
        velocity_neu (common.Velocity): current velocity of the vehicle in the global NEU (North, East, Up) coordinate frame
        velocity_body (common.Velocity): current velocity of the vehicle in the body (forward, right, up)  coordinate frame
        setpoint_info (SetpointInfo): info on the current vehicle setpoint
    """

    home: Optional[common.Location] = None
    global_position: Optional[common.Location] = None
    relative_position: Optional[common.Position] = None
    velocity_neu: Optional[common.Velocity] = None
    velocity_body: Optional[common.Velocity] = None
    setpoint_info: Optional[SetpointInfo] = None


class GimbalStatus(Datatype):
    """Status of a gimbal.

    Attributes:
        id (int): ID of the gimbal
        pose_body (common.Pose): current pose in the body (forward, right, up) reference frame
        pose_neu (common.Pose): current pose in the NEU (North, East, Up) reference frame
    """

    id: Optional[int] = None
    pose_body: Optional[common.Pose] = None
    pose_neu: Optional[common.Pose] = None


class GimbalInfo(Datatype):
    """Info of all attached gimbals.

    Attributes:
        num_gimbals (int): number of connected gimbals
        gimbals (List[GimbalStatus]): list of connected gimbals
    """

    num_gimbals: Optional[int] = None
    gimbals: List[GimbalStatus] = Field(default_factory=list)


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

    id: Optional[int] = None
    type: Optional[ImagingSensorType] = None
    active: Optional[bool] = None
    supports_secondary: Optional[bool] = None
    current_fps: Optional[int] = None
    max_fps: Optional[int] = None
    h_res: Optional[int] = None
    v_res: Optional[int] = None
    channels: Optional[int] = None
    h_fov: Optional[int] = None
    v_fov: Optional[int] = None
    gimbal_mounted: Optional[bool] = None
    gimbal_id: Optional[int] = None


class ImagingSensorStreamStatus(Datatype):
    """Information about all imaging sensor streams.

    Attributes:
        stream_capacity (int): the total number of allowed simultaneously streaming cameras
        num_streams (int): the total number of currently streaming cameras
        primary_cam (int): ID of the primary camera
        secondary_cams (List[int]): IDs of the secondary active cameras
    """

    stream_capacity: Optional[int] = None
    num_streams: Optional[int] = None
    primary_cam: Optional[int] = None
    secondary_cams: List[int] = Field(default_factory=list)


class ImagingSensorInfo(Datatype):
    """Information about all attached imaging sensors.

    Attributes:
        stream_status (ImagingSensorStreamStatus): status of current imaging sensor streams
        sensors (List[ImagingSensorStatus]): list of connected imaging sensors
    """

    stream_status: Optional[ImagingSensorStreamStatus] = None
    sensors: List[ImagingSensorStatus] = Field(default_factory=list)


class AlertInfo(Datatype):
    """Information about all vehicle warning and alerts.

    Attributes:
        battery_warning (BatteryWarning): battery warnings
        gps_warning (GPSWarning): GPS warnings
        magnetometer_warning (MagnetometerWarning): magnetometer warnings
        connection_warning (ConnectionWarning): connection warnings
        compass_warning (CompassWarning): compass warnings
    """

    battery_warning: Optional[BatteryWarning] = None
    gps_warning: Optional[GPSWarning] = None
    magnetometer_warning: Optional[MagnetometerWarning] = None
    connection_warning: Optional[ConnectionWarning] = None
    compass_warning: Optional[CompassWarning] = None


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

    timestamp: Optional[Timestamp] = None
    telemetry_stream_info: Optional[TelemetryStreamInfo] = None
    vehicle_info: Optional[VehicleInfo] = None
    position_info: Optional[PositionInfo] = None
    gimbal_info: Optional[GimbalInfo] = None
    imaging_sensor_info: Optional[ImagingSensorInfo] = None
    alert_info: Optional[AlertInfo] = None


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

    timestamp: Optional[Timestamp] = None
    data: Optional[bytes] = None
    h_res: Optional[int] = None
    v_res: Optional[int] = None
    d_res: Optional[int] = None
    channels: Optional[int] = None
    id: Optional[int] = None


class MissionInfo(Datatype):
    """Information about the current mission.

    Attributes:
        name (str): mission name
        hash (int): mission hash to establish version uniqueness
        age (Timestamp): timestamp of upload
        exec_state (MissionExecState): execution state of the mission
        task_state (str): task state of the mission (plaintext), if active
    """

    name: Optional[str] = None
    hash: Optional[int] = None
    age: Optional[Timestamp] = None
    exec_state: Optional[MissionExecState] = None
    task_state: Optional[str] = None


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

    timestamp: Optional[Timestamp] = None
    telemetry_stream_info: Optional[TelemetryStreamInfo] = None
    mission_info: List[MissionInfo] = Field(default_factory=list)
