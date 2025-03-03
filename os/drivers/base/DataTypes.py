from typing import NamedTuple
from enum import Enum

class Attitude(NamedTuple):
    """
    Holds attitude data for a drone or gimbal.

    :param pitch: Pitch, in degrees
    :type pitch: float, optional
    :param roll: Roll, in degrees
    :type roll: float, optional
    :param yaw: Yaw, in degrees
    :type yaw: float, optional
    """
    pitch: float = None
    roll: float = None
    yaw: float = None


class Velocity(NamedTuple):
    """
    Holds velocity data for the drone in meters per second.

    :param forward: Forward velocity, in meters per second
    :type forward: float, optional
    :param right: Rightward velocity, in meters per second
    :type right: float, optional
    :param down: Downward velocity, in meters per second
    :type down: float, optional
    :param angular: Angular velocity, in degrees per second
    :type angular: float, optional
    """
    forward: float = None
    right: float = None
    down: float = None
    angular: float = None


class RelativePosition(NamedTuple):
    """
    Holds relative position data for the drone in north,
        east, down (NED) coordinates.

    :param n: Offset north, in meters
    :type n: float, optional
    :param e: Offset east, in meters
    :type e: float, optional
    :param d: Offset down, in meters
    :type d: float, optional
    """
    n: float = None
    e: float = None
    d: float = None


class GlobalPosition(NamedTuple):
    """
    Holds global position data for the drone in lattitude, 
        longitude coordinates. Supports altitude as 
        relative or absolute.

    :param latitude: Latitude, in degrees
    :type latitude: float, optional
    :param longitude: Longitude, in degrees
    :type longitude: float, optional
    :param altitude: Altitude above sea level, in meters
    :type altitude: float, optional
    """
    latitude: float = None
    longitude: float = None
    altitude: float = None


class Magnetometer(Enum):
    """
    Status of the drone magnetic sensor.

    UNKNOWN - No information.
    CALIBRATED - No perturbations detected.
    PERTURBATIONS - Perturbations detected, autonomous flight
        still possible.
    CALIBRATION_REQUIRED - Severe perturbations detected, 
        autonomous flight not possible until manual 
        calibration.
    """
    UNKNOWN = 0
    CALIBRATED = 1
    PERTURBATIONS = 2
    CALIBRATION_REQUIRED = 3


class Status(Enum):
    """
    Status of the drone.

    UNKNOWN - No information.
    LANDED - On the ground, disarmed.
    FLYING - Flying.
    RTH - Returning home.
    """
    UNKNOWN = 0
    LANDED = 1
    FLYING = 2
    RTH = 3
