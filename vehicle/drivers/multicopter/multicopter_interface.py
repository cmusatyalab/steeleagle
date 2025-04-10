# General imports
from abc import ABC, abstractmethod
import asyncio
# Protocol imports
from protocol import common_pb2 as common_protocol
# ZeroMQ binding imports
import zmq
import zmq.asyncio

class MulticopterItf(ABC):
    """
    Interface file that describes the quadcopter control API.
    All SteelEagle compatible drones must implement a subset of
    this API to function with the driver module. For unimplemented
    methods, drones are expected to reply with 
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
        Instructs the drone to enter a fail-safe state, which may include
        shutting down motors or entering a controlled descent.

        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def set_home(self, loc: common_protocol.Location) -> common_protocol.ResponseStatus:
        """
        Sets the home (return-to-home) destination for the drone, using
        a protobuf-based Location message.

        :param loc: The desired home location, containing lat, lng, and alt
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
    async def set_velocity(self, vel: common_protocol.Velocity) -> common_protocol.ResponseStatus:
        """
        Sets the drone's target velocity.

        The Velocity message contains forward_vel, right_vel, up_vel, and angle_vel, 
        describing motion in meters per second and angular velocity in degrees per 
        second.

        :param vel: The target velocity in each axis plus angular velocity
        :type vel: :class:`protocol.common.Velocity`
        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def set_global_position(self, loc: common_protocol.Location) -> common_protocol.ResponseStatus:
        """
        Commands the drone to move to a specific global location (lat/lng/absolute alt).

        The Location object may also supply a heading. In this case, the drone will 
        turn towards the provided heading before actuating to the target global position. 
        If no heading is provided, the drone will turn to face its target global position 
        before moving.

        :param loc: The desired GPS location, including latitude, longitude, absolute altitude
        :type loc: :class:`protocol.common.Location
        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def set_relative_position(self, pos: common_protocol.Position) -> common_protocol.ResponseStatus:
        """
        Sets a target position for the drone relative to its initial (takeoff) point,
        in meters. The Position message can include north, east, up, and bearing
        components.

        :param pos: The relative position offsets plus bearing
        :type pos: :class:`protocol.common.Position`
        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def set_heading(self, loc: common_protocol.Location) -> common_protocol.ResponseStatus:
        """
        Sets the heading of the drone to face a provided global position or absolute
        bearing.

        If the Location object supplies a latitude and longitude, the drone will turn
        to face that position. If the Location object only supplies a bearing, the
        drone will turn to face that bearing.
        
        :param loc: The target global position or heading to face
        :type loc: :class:`protocol.common.Location`
        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass

    @abstractmethod
    async def set_gimbal_pose(self, pose: common_protocol.Pose) -> common_protocol.ResponseStatus:
        """
        Sets the gimbal pose of the drone, if it has a gimbal.

        :param pose: The target pose of the gimbal
        :type pose: :class:`protocol.common.Pose`
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
            of length (1 / rate)

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
            of length (1 / rate)

        :param cam_sock: ZeroMQ asynchronous socket to which frames are sent
        :type cam_sock: :class:`zmq.asyncio.Socket`
        :param rate_hz: Rate, in frames per second, at which video is transmitted
        :type rate_hz: int
        :return: A response object indicating success or failure
        :rtype: :class:`protocol.common.ResponseStatus`
        """
        pass
