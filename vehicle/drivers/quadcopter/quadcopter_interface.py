# General imports
from abc import ABC, abstractmethod
import asyncio
# Import SteelEagle protocol
from protocol.steeleagle import dataplane_pb2 as data_protocol
from protocol.steeleagle import controlplane_pb2 as control_protocol
from protocol.steeleagle import common_pb2 as common_protocol
# Import ZeroMQ bindings
import zmq
import zmq.asyncio

class QuadcopterItf(ABC):
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
    async def take_off(self) -> control_protocol.Response:
        """
        Arms the drone (if necessary) and instructs it to take off.

        :return: A response object indicating success or failure
        :rtype: :class:`steeleagle.controlplane.Response`
        """
        pass

    @abstractmethod
    async def land(self) -> control_protocol.Response:
        """
        Instructs the drone to land and disarm.

        :return: A response object indicating success or failure
        :rtype: :class:`steeleagle.controlplane.Response`
        """
        pass

    @abstractmethod
    async def hover(self) -> control_protocol.Response:
       """
       Instructs the drone to hover in place.

       :return: A response object indicating success or failure
       :rtype: :class:`steeleagle.controlplane.Response`
       """
       pass
   
    @abstractmethod
    async def kill(self) -> control_protocol.Response:
        """
        Instructs the drone to enter a fail-safe state, which may include
        shutting down motors or entering a controlled descent.

        :return: A response object indicating success or failure
        :rtype: :class:`steeleagle.controlplane.Response`
        """
        pass

    @abstractmethod
    async def set_home(self, loc: common_protocol.Location) -> control_protocol.Response:
        """
        Sets the home (return-to-home) destination for the drone, using
        a protobuf-based Location message.

        :param loc: The desired home location, containing lat, lng, and alt
        :type loc: :class:`steeleagle.common.Location
        :return: A response object indicating success or failure
        :rtype: :class:`steeleagle.controlplane.Response`
        """
        pass

    @abstractmethod
    async def rth(self) -> control_protocol.Response:
        """
        Commands the drone to return to its previously set home location, following
        the specified behavior configured on the drone's autopilot.

        :return: A response object indicating success or failure
        :rtype: :class:`steeleagle.controlplane.Response`
        """
        pass

    @abstractmethod
    async def set_velocity(self, vel: common_protocol.Velocity) -> control_protocol.Response:
        """
        Sets the drone's velocity using a protobuf-based Velocity message.

        The Velocity message contains forward_vel, right_vel, up_vel, and angle_vel, 
        describing motion in meters per second and angular velocity in degrees per 
        second.

        :param vel: The target velocity in each axis plus angular velocity
        :type vel: :class:`steeleagle.common.Velocity`
        :return: A response object indicating success or failure
        :rtype: :class:`steeleagle.controlplane.Response`
        """
        pass

    @abstractmethod
    async def set_global_position(self, loc: common_protocol.Location) -> control_protocol.Response:
        """
        Commands the drone to move to a specific global location (lat/lng/alt).

        The Location object may also supply a heading. In this case, the drone will 
        turn towards the provided heading before actuating to the target global position. 
        If no heading is provided, the drone will turn to face its target global position 
        before moving.

        :param loc: The desired GPS location, including latitude, longitude, altitude
        :type loc: :class:`steeleagle.common.Location
        :return: A response object indicating success or failure
        :rtype: :class:`steeleagle.controlplane.Response`
        """
        pass

    @abstractmethod
    async def set_relative_position(self, pos: common_protocol.Position) -> control_protocol.Response:
        """
        Sets a target position for the drone relative to its initial (takeoff) point,
        in meters. The Position message can include north, east, up, and bearing
        components.

        :param pos: The relative position offsets plus bearing
        :type pos: :class:`steeleagle.common.Position`
        :return: A response object indicating success or failure
        :rtype: :class:`steeleagle.controlplane.Response`
        """
        pass

    @abstractmethod
    async def set_heading(self, loc: common_protocol.Location) -> control_protocol.Response:
        """
        Sets the heading of the drone to face a provided global position or absolute
        bearing.

        If the Location object supplies a latitude and longitude, the drone will turn
        to face that position. If the Location object only supplies a bearing, the
        drone will turn to face that bearing.
        
        :param loc: The target global position or heading to face
        :type loc: :class:`steeleagle.common.Location`
        :return: A response object indicating success or failure
        :rtype: :class:`steeleagle.controlplane.Response`
        """
        pass

    @abstractmethod
    async def stream_telemetry(self, tel_sock: zmq.asyncio.Socket) -> None:
        """
        Continuously sends telemetry data from the drone to the provided ZeroMQ socket.

        The implementation is expected to:
          - Gather telemetry info (GPS position, battery, velocity, etc.)
          - Populate a protobuf `Telemetry` message
          - Send it to `tel_sock` in a loop until the drone disconnects or streaming stops

        :param tel_sock: ZeroMQ asynchronous socket to which telemetry messages are sent
        :type tel_sock: :class:`zmq.asyncio.Socket`
        :return: None
        """
        pass
    
    @abstractmethod
    async def stream_video(self, cam_sock: zmq.asyncio.Socket) -> None:
        """
        Continuously sends video frames from the drone to the provided ZeroMQ socket.

        The implementation is expected to:
          - Acquire frames from the drone's camera or streaming buffer
          - Serialize them (e.g., as a protobuf `Frame` message)
          - Send them to `cam_sock` in a loop until the drone disconnects or streaming stops

        :param cam_sock: ZeroMQ asynchronous socket to which frames are sent
        :type cam_sock: :class:`zmq.asyncio.Socket`
        :return: None
        """
        pass

