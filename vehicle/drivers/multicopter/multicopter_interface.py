# General imports
from abc import ABC, abstractmethod
import asyncio
# Protocol imports
import common_pb2 as common_protocol
# ZeroMQ binding imports
import zmq
import zmq.asyncio

class MulticopterItf(ABC):
    """
    Interface file that describes the quadcopter control API. All SteelEagle compatible
    drones must implement a subset of this API to function with the driver module.
    For unimplemented methods, drones are expected to reply with
    :class:`protocol.common.ResponseStatus` set to NOTSUPPORTED (3).
    """

    @abstractmethod
    async def get_type(self) -> str:
        """
        Returns the drone type.

        :return: Drone type
        :rtype: str
        """
        pass

    @abstractmethod
    async def connect(self) -> bool:
        """
        Connects to the drone hardware.

        :return: True if successful, False otherwise
        :rtype: bool
        """
        pass

    @abstractmethod
    async def is_connected(self) -> bool:
        """
        Checks whether the drone hardware is currently connected.

        :return: True if connected, False otherwise
        :rtype: bool
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Disconnects from the drone hardware.

        :return: None
        """
        pass

    @abstractmethod
    async def take_off(self) -> common_protocol.ResponseStatus:
        """
        Arms the drone (if necessary) and instructs it to take off.

        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def land(self) -> common_protocol.ResponseStatus:
        """
        Instructs the drone to land and disarm.

        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def hover(self) -> common_protocol.ResponseStatus:
       """
       Instructs the drone to hover in place.

       :return: A response object indicating success or failure
       :rtype: :class:`protocol.common.ResponseStatus`
       """
       pass

    @abstractmethod
    async def kill(self) -> common_protocol.ResponseStatus:
        """
        Instructs the drone to enter a fail-safe state, which may include shutting down
        motors or entering a controlled descent.

        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def set_home(self, loc: common_protocol.Location) -> common_protocol.ResponseStatus:
        """
        Sets the home global location destination (latitude, longitude, absolute or relative
        altitude in meters) for the drone. If an altitude is provided, the drone will attempt
        to hover at this altitude. Otherwise, it will automatically land if a return-to-home
        is triggered.

        :param loc: The desired home location, containing lat, lng, and absolute altitude
        :type loc: :class:`protocol.common.Location
        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def rth(self) -> common_protocol.ResponseStatus:
        """
        Commands the drone to return to its previously set home location, following
        the specified behavior configured on the drone's autopilot.

        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def set_global_position(self, loc: common_protocol.Location) -> common_protocol.ResponseStatus:
        """
        Commands the drone to move to a specific global location (latitude, longitude,
        absolute or relative altitude in meters). If both absolute (MSL) and relative
        (relative to take off) altitude are provided, absolute will be prioritized.
        Both a target latitude and target longitude must be provided.

        The Location object may also supply a heading. In this case, the drone will
        turn to the provided heading before actuating to the target global position.
        If no heading is provided, the drone will turn to face its target global position
        before moving.

        :param loc: The desired GPS location, including latitude, longitude, absolute
            or relative altitude in meters, heading in degrees
        :type loc: :class:`protocol.common.Location`
        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def set_relative_position_enu(self, pos: common_protocol.PositionENU) \
            -> common_protocol.ResponseStatus:
        """
        Sets a target position for the drone relative to its initial (takeoff) point,
        in meters. The target position is expressed with respect to the ENU (east, north, up)
        global reference frame.

        :param pos: The relative position offsets plus heading, in ENU global coordinates
        :type pos: :class:`protocol.common.PositionENU`
        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def set_relative_position_body(self, pos: common_protocol.PositionBody) \
            -> common_protocol.ResponseStatus:
        """
        Sets a target position for the drone relative to its current position, in meters.
        The target position is expressed with respect to the FRU (forward, right, up)
        body reference frame.

        :param pos: The relative position offsets plus heading, in FRU body coordinates
        :type pos: :class:`protocol.common.PositionBody`
        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def set_velocity_enu(self, vel: common_protocol.VelocityENU) -> common_protocol.ResponseStatus:
        """
        Sets the drone's target velocity. The velocity target is expressed with respect to
        the ENU (east, north, up) global reference frame.

        The Velocity message contains north_vel, east_vel, up_vel, and angle_vel,
        describing motion in meters per second and angular velocity in degrees per
        second.

        :param vel: The target velocity in each axis plus angular velocity, in the ENU global
            reference frame
        :type vel: :class:`protocol.common.VelocityENU`
        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def set_velocity_body(self, vel: common_protocol.VelocityBody) -> common_protocol.ResponseStatus:
        """
        Sets the drone's target velocity. The velocity target is expressed with respect to
        the FRU (forward, right, up) body reference frame.

        The Velocity message contains forward_vel, right_vel, up_vel, and angle_vel,
        describing motion in meters per second and angular velocity in degrees per
        second.

        :param vel: The target velocity in each axis plus angular velocity, in the FRU body
            reference frame
        :type vel: :class:`protocol.common.VelocityBody`
        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def set_heading(self, loc: common_protocol.Location) -> common_protocol.ResponseStatus:
        """
        Sets the heading of the drone to face a provided global position (latitude, longitude)
        which is used to calculate a target bearing or an absolute heading (degrees).
        Ignores any provided altitude.

        If the Location object supplies a heading, the drone will turn to face that heading.
        If the Location object instead supplies a latitude and longitude, the drone will turn
        to face that position. Absolute heading is prioritized over position.

        :param loc: The target global position (latitude, longitude) or heading (degrees) to face
        :type loc: :class:`protocol.common.Location`
        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def set_gimbal_pose(self, pose: common_protocol.PoseBody) -> common_protocol.ResponseStatus:
        """
        Sets the gimbal pose of the drone, if it has a gimbal, with respect to the body frame
        of reference.

        :param pose: The target pose of the gimbal, with respect to the body frame of reference
        :type pose: :class:`protocol.common.PoseBody`
        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def stream_telemetry(self, tel_sock: zmq.asyncio.Socket, rate_hz: int) -> None:
        """
        Continuously sends telemetry data from the drone to the provided ZeroMQ socket.

        The implementation is expected to:
          - Gather telemetry info (global position, battery, velocity, etc.)
          - Populate a protobuf `Telemetry` message
          - Send it to `tel_sock` in a loop until the drone disconnects or streaming stops,
            while yielding execution at the end of each iteration using `asyncio.sleep()`
            of length (1 / rate_hz)

        :param tel_sock: ZeroMQ asynchronous socket to which telemetry messages are sent
        :type tel_sock: :class:`zmq.asyncio.Socket`
        :param rate_hz: Rate, in messages per second, at which telemetry is transmitted
        :type rate_hz: int
        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def stream_video(self, cam_sock: zmq.asyncio.Socket, rate_hz: int) -> None:
        """
        Continuously sends video frames from the drone to the provided ZeroMQ socket.

        The implementation is expected to:
          - Acquire frames from the drone's camera or streaming buffer
          - Serialize them (e.g., as a protobuf `Frame` message)
          - Send them to `cam_sock` in a loop until the drone disconnects or streaming stops,
            while yielding execution at the end of each iteration using `asyncio.sleep()`
            of length (1 / rate_hz)

        :param cam_sock: ZeroMQ asynchronous socket to which frames are sent
        :type cam_sock: :class:`zmq.asyncio.Socket`
        :param rate_hz: Rate, in frames per second, at which video is transmitted
        :type rate_hz: int
        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass
