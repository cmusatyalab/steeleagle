from enum import Enum

from pydantic import Field

from . import common
from ._base import Datatype
from .duration import Duration
from .timestamp import Timestamp


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

    current_frequency: int | None = None
    max_frequency: int | None = None
    uptime: Duration | None = None


class BatteryInfo(Datatype):
    """Information about the vehicle battery.

    Attributes:
        percentage (int): battery level [0-100]%
    """

    percentage: int | None = None


class GPSInfo(Datatype):
    """Information about the vehicle GPS fix.

    Attributes:
        satellites (int): number of satellites used in GPS fix
    """

    satellites: int | None = None


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

    name: str | None = None
    model: str | None = None
    manufacturer: str | None = None
    motion_status: MotionStatus | None = None
    battery_info: BatteryInfo | None = None
    gps_info: GPSInfo | None = None
    comms_info: CommsInfo | None = None


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

    position_body_sp: common.Position | None = None
    position_neu_sp: common.Position | None = None
    global_sp: common.Location | None = None
    velocity_body_sp: common.Velocity | None = None
    velocity_neu_sp: common.Velocity | None = None


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

    home: common.Location | None = None
    global_position: common.Location | None = None
    relative_position: common.Position | None = None
    velocity_neu: common.Velocity | None = None
    velocity_body: common.Velocity | None = None
    setpoint_info: SetpointInfo | None = None


class GimbalStatus(Datatype):
    """Status of a gimbal.

    Attributes:
        id (int): ID of the gimbal
        pose_body (common.Pose): current pose in the body (forward, right, up) reference frame
        pose_neu (common.Pose): current pose in the NEU (North, East, Up) reference frame
    """

    id: int | None = None
    pose_body: common.Pose | None = None
    pose_neu: common.Pose | None = None


class GimbalInfo(Datatype):
    """Info of all attached gimbals.

    Attributes:
        num_gimbals (int): number of connected gimbals
        gimbals (List[GimbalStatus]): list of connected gimbals
    """

    num_gimbals: int | None = None
    gimbals: list[GimbalStatus] = Field(default_factory=list)


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

    id: int | None = None
    type: ImagingSensorType | None = None
    active: bool | None = None
    supports_secondary: bool | None = None
    current_fps: int | None = None
    max_fps: int | None = None
    h_res: int | None = None
    v_res: int | None = None
    channels: int | None = None
    h_fov: int | None = None
    v_fov: int | None = None
    gimbal_mounted: bool | None = None
    gimbal_id: int | None = None


class ImagingSensorStreamStatus(Datatype):
    """Information about all imaging sensor streams.

    Attributes:
        stream_capacity (int): the total number of allowed simultaneously streaming cameras
        num_streams (int): the total number of currently streaming cameras
        primary_cam (int): ID of the primary camera
        secondary_cams (List[int]): IDs of the secondary active cameras
    """

    stream_capacity: int | None = None
    num_streams: int | None = None
    primary_cam: int | None = None
    secondary_cams: list[int] = Field(default_factory=list)


class ImagingSensorInfo(Datatype):
    """Information about all attached imaging sensors.

    Attributes:
        stream_status (ImagingSensorStreamStatus): status of current imaging sensor streams
        sensors (List[ImagingSensorStatus]): list of connected imaging sensors
    """

    stream_status: ImagingSensorStreamStatus | None = None
    sensors: list[ImagingSensorStatus] = Field(default_factory=list)


class AlertInfo(Datatype):
    """Information about all vehicle warning and alerts.

    Attributes:
        battery_warning (BatteryWarning): battery warnings
        gps_warning (GPSWarning): GPS warnings
        magnetometer_warning (MagnetometerWarning): magnetometer warnings
        connection_warning (ConnectionWarning): connection warnings
        compass_warning (CompassWarning): compass warnings
    """

    battery_warning: BatteryWarning | None = None
    gps_warning: GPSWarning | None = None
    magnetometer_warning: MagnetometerWarning | None = None
    connection_warning: ConnectionWarning | None = None
    compass_warning: CompassWarning | None = None


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

    timestamp: Timestamp | None = None
    telemetry_stream_info: TelemetryStreamInfo | None = None
    vehicle_info: VehicleInfo | None = None
    position_info: PositionInfo | None = None
    gimbal_info: GimbalInfo | None = None
    imaging_sensor_info: ImagingSensorInfo | None = None
    alert_info: AlertInfo | None = None


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

    timestamp: Timestamp | None = None
    data: bytes | None = None
    h_res: int | None = None
    v_res: int | None = None
    d_res: int | None = None
    channels: int | None = None
    id: int | None = None


class MissionInfo(Datatype):
    """Information about the current mission.

    Attributes:
        name (str): mission name
        hash (int): mission hash to establish version uniqueness
        age (Timestamp): timestamp of upload
        exec_state (MissionExecState): execution state of the mission
        task_state (str): task state of the mission (plaintext), if active
    """

    name: str | None = None
    hash: int | None = None
    age: Timestamp | None = None
    exec_state: MissionExecState | None = None
    task_state: str | None = None


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

    timestamp: Timestamp | None = None
    telemetry_stream_info: TelemetryStreamInfo | None = None
    mission_info: list[MissionInfo] = Field(default_factory=list)
