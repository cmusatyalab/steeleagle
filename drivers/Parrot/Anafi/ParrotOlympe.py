# General imports
import math
import time
import asyncio
import logging
from enum import Enum
import numpy as np
import os
import grpc
import zmq
import zmq.asyncio
# SDK imports (Olympe)
import olympe
from olympe import Drone
from olympe.messages.ardrone3.Piloting import TakeOff, Landing
from olympe.messages.ardrone3.Piloting import PCMD, moveTo, moveBy
from olympe.messages.move import extended_move_to
from olympe.messages.rth import set_custom_location, return_to_home, custom_location, state, takeoff_location
import olympe.enums.rth as rth_state
from olympe.messages.common.CommonState import BatteryStateChanged
from olympe.messages.ardrone3.SpeedSettingsState import MaxRotationSpeedChanged
from olympe.messages.ardrone3.PilotingState import HeadingLockedStateChanged, AttitudeChanged, GpsLocationChanged, AltitudeChanged, FlyingStateChanged, SpeedChanged, moveToChanged, moveByChanged
from olympe.messages.ardrone3.GPSSettingsState import GPSFixStateChanged
from olympe.messages.alarms import alarms
from olympe.messages.ardrone3.GPSState import NumberOfSatelliteChanged
from olympe.messages.gimbal import set_target, attitude
import olympe.enums.move as move_mode
# Protocol imports
import common_pb2 as common_protocol
from common_pb2 import Request, Response
from services.control_service_pb2_grpc import ControlServicer
from services import control_service_pb2 as control_protocol
from messages import telemetry_pb2 as telemetry_protocol
from google.protobuf.duration_pb2 import Duration
from google.protobuf.timestamp_pb2 import Timestamp
    
# Streaming imports
import threading
import cv2
import queue

# Utility imports
logger = logging.getLogger("Parrot/Olympe")

TELEMETRY_SOCK = 'ipc:///tmp/driver_telem.sock'
IMAGERY_SOCK = 'ipc:///tmp/imagery.sock'

telemetry_sock = zmq.Context().socket(zmq.PUB)
telemetry_sock.bind(TELEMETRY_SOCK)

cam_sock = zmq.Context().socket(zmq.PUB)
cam_sock.bind(IMAGERY_SOCK)

def generate_response(resp_type, resp_string=""):
    '''
    Generates a protobuf response object for an RPC given a
    response type and optional response string.
    '''
    return Response(
            status=resp_type,
            response_string=resp_string,
            timestamp=Timestamp().GetCurrentTime()
            )

class ParrotOlympeDrone(ControlServicer):

    class FlightMode(Enum):
        LOITER = 'LOITER'
        TAKEOFF_LAND = 'TAKEOFF_LAND'
        VELOCITY_BODY = 'VELOCITY_BODY'
        VELOCITY_NEU = 'VELOCITY_NEU'
        GUIDED_BODY = 'GUIDED_BODY'
        GUIDED_NEU = 'GUIDED_NEU'

    def __init__(self, drone_id, connection_string, **kwargs):
        self._drone_id = drone_id
        self._connection_string = connection_string
        self._kwargs = kwargs
        # Drone flight modes and setpoints
        self._setpoint = common_protocol.Position()
        # Set PID values for the drone
        self._forward_pid_values = {}
        self._right_pid_values = {}
        self._up_pid_values = {}
        self._pid_task = None
        self._mode = ParrotOlympeDrone.FlightMode.LOITER
        self._gimbal_id = 0
        # Create thread holders
        self._streaming_thread = None
        self._telemetry_thread = None

    ''' Interface methods '''
    async def Connect(self, request, context):
        try:
            self._drone = Drone(self._connection_string)
            result = self._drone.connect()
            if not result:
                self._drone = None
                await context.abort(grpc.StatusCode.INTERNAL, "Drone connection failed")
            logger.info("Completed connection to digital drone...")
            return generate_response(
                resp_type=common_protocol.ResponseStatus.COMPLETED,
                resp_string="Connected to digital drone",
            )    
        except Exception as e:
            logger.error(f"Error occurred while connecting to digital drone: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")

    async def Disconnect(self, request, context):
        try:
            if not self._is_connected():
                logger.warning("Drone is already disconnected.")
                return generate_response(
                    resp_type=common_protocol.ResponseStatus.COMPLETED,
                    resp_string="Drone is already disconnected.",
                )

            result = self._drone.disconnect()
            if not result:
                logger.error("Failed to properly disconnect from digital drone...")
                await context.abort(
                    grpc.StatusCode.INTERNAL, "Drone disconnection failed"
                )

            logger.info("Completed disconnection from digital drone...")
            return generate_response(
                resp_type=common_protocol.ResponseStatus.COMPLETED,
                resp_string="Disconnected from digital drone",
            )
        except Exception as e:
            logger.error(f"Error occurred while disconnecting from digital drone: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")

    async def Arm(self, request, context):
        await context.abort(
            grpc.StatusCode.UNIMPLEMENTED, "Arm not implemented for digital drone"
        )

    async def Disarm(self, request, context):
        await context.abort(
            grpc.StatusCode.UNIMPLEMENTED, "Disarm not implemented for digital drone"
        )

    async def TakeOff(self, request, context):
        logger.info("Initiating takeoff sequence...")
        try:
            yield generate_response(resp_type=common_protocol.ResponseStatus.IN_PROGRESS, resp_string="Initiating takeoff...")
            logger.info("Switching to TAKEOFF_LAND mode...")
            await self._switch_mode(ParrotOlympeDrone.FlightMode.TAKEOFF_LAND)
            logger.info("Takeoff command sent to drone...")
            self._drone(TakeOff())

            # Elevate up to take off altitude 
            while not self._is_rel_altitude_reached(request.take_off_altitude) \
                    and not self._get_altitude_rel() >= request.take_off_altitude:

                # Elevate at 30% throttle
                self._drone(PCMD(
                    1,
                    0,
                    0,
                    0,
                    30,
                    timestampAndSeqNum=0
                    )).success()

                yield generate_response(resp_type=common_protocol.ResponseStatus.IN_PROGRESS, resp_string="elevating...")
                await asyncio.sleep(0.01)

            # Halt drone at altitude
            self._drone(PCMD(
                1,
                0,
                0,
                0,
                0,
                timestampAndSeqNum=0
                )).success()

            # Send IN_PROGRESS stream
            while not self._is_hovering(): 
                logger.info("Waiting for drone to reach hover state...")
                yield generate_response(resp_type=common_protocol.ResponseStatus.IN_PROGRESS, resp_string="checking hovering state...")
                await asyncio.sleep(0.1) 
            await self._switch_mode(ParrotOlympeDrone.FlightMode.LOITER)
            logger.info(f"checking if hovering... {self._is_hovering()}")  
            yield generate_response(resp_type=common_protocol.ResponseStatus.IN_PROGRESS, resp_string="Hovering...")

            # Send COMPLETED
            yield generate_response(resp_type=common_protocol.ResponseStatus.COMPLETED, resp_string="Takeoff successful")
            logger.info("Takeoff sequence completed successfully.")

        except Exception as e:
            logger.error(f"Error occurred during takeoff: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")

    async def Land(self, request, context):
        try:
            yield generate_response(
                resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                resp_string="Initiating landing...",
            )
            await self._switch_mode(ParrotOlympeDrone.FlightMode.TAKEOFF_LAND)
            self._drone(Landing()).success()

            while not self._is_landed():
                yield generate_response(
                    resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                    resp_string="Landing...",
                )
                await asyncio.sleep(0.1)

            await self._switch_mode(ParrotOlympeDrone.FlightMode.LOITER)
            yield generate_response(
                resp_type=common_protocol.ResponseStatus.COMPLETED,
                resp_string="Landing successful",
            )
        except Exception as e:
            logger.error(f"Error occurred during landing: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")


    async def Hold(self, request, context):
        try:
            yield generate_response(
                resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                resp_string="Initiating hold...",
            )
            await self._switch_mode(ParrotOlympeDrone.FlightMode.LOITER)

            # Send the command
            self._drone(PCMD(
                1,
                0,
                0,
                0,
                0,
                timestampAndSeqNum=0
                )).success()

            # Send IN_PROGRESS stream
            while not self._is_hovering():
                yield generate_response(
                    resp_type = common_protocol.ResponseStatus.IN_PROGRESS,
                    resp_string = "checking hovering state...",
                )
            # Send COMPLETED
            yield generate_response(
                    resp_type=common_protocol.ResponseStatus.COMPLETED,
                    resp_string="Hold successful",
            )
        except Exception as e:
            logger.error(f"Error occurred during hold: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")

    async def Kill(self, request, context):
        await context.abort(
            grpc.StatusCode.UNIMPLEMENTED, "Kill not implemented for digital drone"
        )

    async def SetHome(self, request, context):
        # Send the command
        try:
            # Extract home data
            location = request.location
            lat = location.latitude
            lon = location.longitude
            alt = location.altitude
            self._drone(set_custom_location(lat, lon, alt)).wait().success()
            # Send COMPLETED
            yield generate_response(
                resp_type=common_protocol.ResponseStatus.COMPLETED,
                resp_string="Returned to home successfully",
            )
        except Exception as e:
            logger.error(f"Error occurred during hold: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")

        
    async def ReturnToHome(self, request, context):
        try:
            yield generate_response(
                resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                resp_string="Initiating return to home...",
            )
            
            await self._switch_mode(ParrotOlympeDrone.FlightMode.TAKEOFF_LAND)

            # Send the command
            self._drone(return_to_home()).success()
            await asyncio.sleep(1)

            # Send an IN_PROGRESS stream
            while not self._is_home_reached():
                yield generate_response(
                    resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                    resp_string="Returning to home...",
                )
                await asyncio.sleep(1)

            # Send COMPLETED
            await self._switch_mode(ParrotOlympeDrone.FlightMode.LOITER)
            yield generate_response(
                resp_type=common_protocol.ResponseStatus.COMPLETED,
                resp_string="Returned to home successfully",
            )
 
        except Exception as e:
            logger.error(f"Error occurred during return to home: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")


    async def SetGlobalPosition(self, request, context):
        try:
            yield generate_response(
                resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                resp_string="Initiating setting global position...",
            )
            # Extract location data
            location = request.location
            lat = location.latitude
            lon = location.longitude
            alt = location.altitude
            bearing = location.heading
            logger.info(f"SetGlobalPosition: lat={lat}, lon={lon}, alt={alt}, bearing={bearing}")
            alt_mode = request.altitude_mode
            hdg_mode = request.heading_mode
            max_velocity = request.max_velocity
            self._setpoint = location

            # Olympe only accepts relative altitude, so convert absolute to
            # relative altitude in case that is the location mode
            if alt_mode == control_protocol.AltitudeMode.ABSOLUTE:
                altitude = alt - self._get_global_position().altitude \
                        + self._get_altitude_rel()
            else:
                altitude = alt
            
            # Set the heading mode and bearing appropriately
            if hdg_mode == control_protocol.HeadingMode.TO_TARGET:
                heading_mode = move_mode.orientation_mode.to_target
                await self._switch_mode(ParrotOlympeDrone.FlightMode.GUIDED_NEU)
            elif hdg_mode == control_protocol.HeadingMode.HEADING_START:
                heading_mode = move_mode.orientation_mode.heading_start
                await self._switch_mode(ParrotOlympeDrone.FlightMode.GUIDED_BODY)

            
            
            # Check if max velocities are provided
            if max_velocity.x_vel or \
                    max_velocity.y_vel or \
                    max_velocity.z_vel or \
                    max_velocity.angular_vel:
                # Set max velocities for transit
                logger.info(f"Setting max velocities: x={max_velocity.x_vel}, y={max_velocity.y_vel}, z={max_velocity.z_vel}, angular={max_velocity.angular_vel}")
                logger.info(f"latitude: {altitude}, lon: {lon}, alt: {altitude}, heading_mode: {heading_mode}, bearing: {bearing}")
                self._drone(
                    extended_move_to(
                        lat,
                        lon,
                        altitude,
                        heading_mode,
                        bearing,
                        max(max_velocity.x_vel, max_velocity.y_vel),
                        max_velocity.z_vel,
                        max_velocity.angular_vel
                        )
                ).success()
            else:
                self._drone(
                    moveTo(
                        lat,
                        lon,
                        altitude,
                        heading_mode,
                        bearing
                        )
                ).success()
            
            # Sleep momentarily to prevent an early exit
            await asyncio.sleep(1)

            # Send an IN_PROGRESS stream
            while not self._is_move_to_done():
                yield generate_response(
                    resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                    resp_string="Checking moving state...",
                )
            # Check to see if we actually reached our desired position
            if self._is_global_position_reached(location, alt_mode):
                yield generate_response(
                    resp_type=common_protocol.ResponseStatus.COMPLETED,
                    resp_string="Reached target location successfully",
                )
            else:
                # Send FAILED
                await context.abort(
                    grpc.StatusCode.INTERNAL, "Failed to reach target location"
                )
        except Exception as e:
            logger.error(f"Error occurred during SetGlobalPosition: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")


    async def SetRelativePosition(self, request, context):
        await context.abort(
            grpc.StatusCode.UNIMPLEMENTED,
            "SetRelativePosition in NEU frame not implemented for digital drone",
        )

    async def Joystick(self, request, context):
        try:
            # Extract velocity data
            self._setpoint = request.velocity
            await self._switch_mode(ParrotOlympeDrone.FlightMode.VELOCITY_BODY)

            # Restart PID task if it isn't already running
            if self._pid_task is None:
                self._pid_task = asyncio.create_task(self._velocity_pid())

            return generate_response(common_protocol.ResponseStatus.COMPLETED)
        except Exception as e:
            logger.error(f"Error occurred during Joystick: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")

    async def SetVelocity(self, request, context):
        try:
            yield generate_response(
                resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                resp_string="Initiating setting velocity...",
            )
            
            # Extract velocity data
            self._setpoint = request.velocity
            if not request.frame or request.frame == control_protocol.ReferenceFrame.NEU:
                await self._switch_mode(ParrotOlympeDrone.FlightMode.VELOCITY_NEU)
            elif request.frame == control_protocol.ReferenceFrame.BODY:
                await self._switch_mode(ParrotOlympeDrone.FlightMode.VELOCITY_BODY)

            # Restart PID task if it isn't already running
            if self._pid_task is None:
                self._pid_task = asyncio.create_task(self._velocity_pid())

            # Send an IN_PROGRESS stream
            if self._mode == ParrotOlympeDrone.FlightMode.VELOCITY_NEU:
                while not self._is_velocity_neu_reached(self._setpoint):
                    yield generate_response(
                            resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                            resp_string="Setting velocity...",
                        )
                    await asyncio.sleep(0.1)
            else:
                while not self._is_velocity_body_reached(self._setpoint):
                    yield generate_response(
                            resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                            resp_string="Setting velocity...",
                        )
                    await asyncio.sleep(0.1)

            # Send success
            yield generate_response(
                resp_type=common_protocol.ResponseStatus.COMPLETED,
                resp_string="Velocity set successfully",
            )
        except Exception as e:
            logger.error(f"Error occurred during SetVelocity: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")

    async def SetHeading(self, request, context):
        try:
            yield generate_response(
                        resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                        resp_string="Initiating setting heading...",
                    )
            
            # Extract location data
            location = request.location
            lat = location.latitude
            lon = location.longitude
            bearing = location.bearing
            heading_mode = location.heading_mode

            # Select target based on mode
            if heading_mode == control_protocol.HeadingMode.HEADING_START:
                target = bearing
            else:
                global_position = self._get_global_position()
                target = self._calculate_bearing(
                        global_position.latitude,
                        global_position.longitude,
                        lat,
                        lon
                        )
            
            offset = math.radians(bearing - target)

            self._drone(moveBy(0.0, 0.0, 0.0, offset)).success()

            # Send an IN_PROGRESS stream
            while not self._is_heading_reached(target) \
                    and self._get_compass_state() != 2:
                yield generate_response(
                    resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                    resp_string="Setting heading...",
                )
                await asyncio.sleep(0.1)

            if self._get_compass_state() == 1:
                await context.abort(
                    grpc.StatusCode.INTERNAL, "Weak heading lock, heading may be inaccurate"
                )
                
            elif self._get_compass_state() == 2:
                await context.abort(
                    grpc.StatusCode.INTERNAL, "No Heading lock"
                )

            # Send COMPLETED
            yield generate_response(
                resp_type=common_protocol.ResponseStatus.COMPLETED,
                resp_string="Heading set successfully",
            )
        except Exception as e:
            logger.error(f"Error occurred during SetHeading: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")

    async def SetGimbalPose(self, request, context):
        try:
            yield generate_response(
                    resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                    resp_string="Initializing setting gimbal pose...",
            )

            # Extract pose data
            gimbal_id = request.gimbal_id
            pose = request.pose
            yaw = pose.yaw
            pitch = pose.pitch
            roll = pose.roll
            control_mode = request.pose_mode 

            # Actuate the gimbal depending on mode
            if control_mode == control_protocol.PoseMode.ANGLE:
                target_yaw = yaw
                target_pitch = pitch
                target_roll = roll
                
                self._drone(set_target(
                    gimbal_id=gimbal_id,
                    control_mode="position",
                    yaw_frame_of_reference="absolute",
                    yaw=yaw,
                    pitch_frame_of_reference="absolute",
                    pitch=pitch,
                    roll_frame_of_reference="absolute",
                    roll=roll)
                ).success()
            elif control_mode == control_protocol.PoseMode.OFFSET:
                current_gimbal = self._get_gimbal_pose_neu()
                if request.frame == control_protocol.ReferenceFrame.BODY:
                    current_gimbal = self._get_gimbal_pose_body()
                target_yaw = current_gimbal['yaw'] + yaw
                target_pitch = current_gimbal['pitch'] + pitch
                target_roll = current_gimbal['roll'] + roll
                
                self._drone(set_target(
                    gimbal_id=gimbal_id,
                    control_mode="position",
                    yaw_frame_of_reference="relative",
                    yaw=target_yaw,
                    pitch_frame_of_reference="relative",
                    pitch=target_pitch,
                    roll_frame_of_reference="relative",
                    roll=target_roll)
                ).success()
            else: #PoseMode == Velocity?
                target_yaw = None
                target_pitch = None
                target_roll = None

                self._drone(set_target(
                    gimbal_id=gimbal_id,
                    control_mode="velocity",
                    yaw_frame_of_reference="relative",
                    yaw=yaw,
                    pitch_frame_of_reference="relative",
                    pitch=pitch,
                    roll_frame_of_reference="relative",
                    roll=roll)
                ).success()

            if control_mode != control_protocol.PoseMode.VELOCITY:
                # Send an IN_PROGRESS stream
                while not self._is_gimbal_pose_body_reached(
                        target_yaw,
                        target_pitch,
                        target_roll
                        ):
                    yield generate_response(
                        resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                        resp_string="Setting gimbal pose...",
                    )
                    await asyncio.sleep(0.1)
            else:
                # We cannot check the velocity of the gimbal from Olympe
                pass        

            # Send COMPLETED
            yield generate_response(
                    resp_type=common_protocol.ResponseStatus.COMPLETED,
                    resp_string="Gimbal pose set successfully",
                )
        except Exception as e:
            logger.error(f"Error occurred during SetGimbalPose: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")

    async def ConfigureImagingSensorStream(self, request, context):
        if not self._streaming_thread:
            self._streaming_thread = ParrotOlympeDrone.PDRAWImageStreamingThread(self._drone, self, cam_sock)
            self._streaming_thread.configure(request)
            self._streaming_thread.start()
            logger.info("Started image streaming thread...")
        return generate_response(common_protocol.ResponseStatus.COMPLETED)

    async def ConfigureTelemetryStream(self, request, context):
        if not self._telemetry_thread:
            self._telemetry_thread = ParrotOlympeDrone.TelemetryStreamingThread(self, telemetry_sock)
            self._telemetry_thread.configure(request)
            self._telemetry_thread.start()
            logger.info("Started telemetry streaming thread...")
        return generate_response(common_protocol.ResponseStatus.COMPLETED)

    ''' Telemetry methods '''
    def _get_name(self):
        return self._drone_id

    def _get_flying_state(self):
        state = self._drone.get_state(FlyingStateChanged)["state"]
        if state == "motor_ramping":
            return 1 # Ramping
        elif state == "hovering":
            return 2 # Idle
        elif state == "flying" or state == "landing" or state == "takingoff":
            return 3 # In Transit
        else:
            return 0 # Motors Off

    def _get_home_position(self):
        try:
            loc = self._drone.get_state(custom_location)
        except:
            loc = self._drone.get_state(takeoff_location)
        location = common_protocol.Location()
        location.latitude = loc["latitude"]
        location.longitude = loc["longitude"]
        return location

    def _get_global_position(self):
        loc = self._drone.get_state(GpsLocationChanged)
        location = common_protocol.Location()
        location.latitude = loc["latitude"]
        location.longitude = loc["longitude"]
        location.altitude = loc["altitude"]
        location.heading = self._get_heading()
        return location

    def _get_gps_state(self):
        state = self._drone.get_state(GPSFixStateChanged)
        sats = self._drone._get_satellites()
        if not state["fixed"]:
            return telemetry_protocol.GPSWarning.NO_FIX
        elif sats < 10:
            return telemetry_protocol.GPSWarning.WEAK_SIGNAL
        else:
            return telemetry_protocol.GPSWarning.NO_GPS_WARNING

    def _get_altitude_rel(self):
        return self._drone.get_state(AltitudeChanged)["altitude"]

    def _get_magnetometer_state(self):
        mag = self._drone(alarms(type=3, status=1, _policy='check'))
        if mag:
            return telemetry_protocol.MagnetometerWarning.PERTURBATION
        else:
            return telemetry_protocol.MagnetometerWarning.NO_MAGNETOMETER_WARNING

    def _get_battery_percentage(self):
        return self._drone.get_state(BatteryStateChanged)["percent"]

    def _get_satellites(self):
        try:
            sats = self._drone.get_state(NumberOfSatelliteChanged)["numberOfSatellite"]
            return sats if sats else 0
        except:
            return 0

    def _get_heading(self):
        return math.degrees(self._drone.get_state(AttitudeChanged)["yaw"])

    def _get_velocity_neu(self):
        ned = self._drone.get_state(SpeedChanged)
        velocity = common_protocol.Velocity()
        velocity.x_vel = ned["speedX"]
        velocity.y_vel = ned["speedY"]
        velocity.z_vel = ned["speedZ"] * -1
        return velocity

    def _get_velocity_body(self):
        neu = self._get_velocity_neu()
        vec = np.array([neu.x_vel, neu.y_vel], dtype=float)
        vecf = np.array([0.0, 1.0], dtype=float)

        hd = (self._get_heading()) + 90
        fw = np.radians(hd)
        c, s = np.cos(fw), np.sin(fw)
        R1 = np.array(((c, -s), (s, c)))
        vecf = np.dot(R1, vecf)

        vecr = np.array([0.0, 1.0], dtype=float)
        rt = np.radians(hd + 90)
        c, s = np.cos(rt), np.sin(rt)
        R2 = np.array(((c,-s), (s, c)))
        vecr = np.dot(R2, vecr)

        velocity = common_protocol.Velocity()
        velocity.x_vel = np.dot(vec, vecf) * -1
        velocity.y_vel = np.dot(vec, vecr) * -1
        velocity.z_vel = neu.z_vel
        return velocity

    def _get_gimbal_info(self):
        # TODO: Must be implemented for each drone
        return telemetry_protocol.GimbalInfo()

    def _get_gimbal_pose_body(self):
        gimbal_id = self._gimbal_id
        pose = common_protocol.Pose()
        pose.yaw = \
            self._drone.get_state(attitude)[gimbal_id]["yaw_relative"]
        pose.pitch = \
            self._drone.get_state(attitude)[gimbal_id]["pitch_relative"]
        pose.roll = \
            self._drone.get_state(attitude)[gimbal_id]["roll_relative"]
        return pose
    
    def _get_gimbal_pose_neu(self):
        gimbal_id = self._gimbal_id
        pose = common_protocol.Pose()
        pose.yaw = \
            self._drone.get_state(attitude)[gimbal_id]["yaw_absolute"]
        pose.pitch = \
            self._drone.get_state(attitude)[gimbal_id]["pitch_absolute"]
        pose.roll = \
            self._drone.get_state(attitude)[gimbal_id]["roll_absolute"]
        return pose

    def _get_imaging_sensor_info(self):
        # TODO: Must be implemented for each drone
        return telemetry_protocol.ImagingSensorInfo()

    def _get_compass_state(self):
        state = self._drone.get_state(HeadingLockedStateChanged)["state"]
        if state == "OK":
            return telemetry_protocol.CompassWarning.NO_COMPASS_WARNING
        elif state == "WARNING":
            return telemetry_protocol.CompassWarning.WEAK_HEADING_LOCK
        else:
            return telemetry_protocol.CompassWarning.NO_HEADING_LOCK

    def _get_alert_info(self):
        alert_info = telemetry_protocol.AlertInfo()

        battery = self._drone._get_battery_percentage()
        gps = self._drone._get_gps_state()
        magnetometer = self._drone._get_magnetometer_state()
        compass = self._drone._get_compass_state()

        if battery <= 30:
            alert_info.battery_warning = \
                telemetry_protocol.BatteryWarning.LOW
        elif battery <= 15:
            alert_info.battery_warning = \
                telemetry_protocol.BatteryWarning.CRITICAL

        alert_info.gps_warning = gps
        alert_info.magnetometer_warning = magnetometer
        alert_info.compass_warning = compass

        return alert_info

    ''' Actuation methods '''
    async def _switch_mode(self, mode):
        if self._mode == mode or \
                (self._mode == ParrotOlympeDrone.FlightMode.TAKEOFF_LAND \
                and mode != ParrotOlympeDrone.FlightMode.LOITER):
            return
        else:
            # Cancel the running PID task
            if self._pid_task:
                self._pid_task.cancel()
                await self._pid_task
            self._pid_task = None
            self._mode = mode

    ''' Coroutine methods '''
    async def _velocity_pid(self):
        '''
        Parrot Olympe does not support set velocity commands like MAVLink
        drones do. Instead, it provides a virtual joystick API that can
        send angular tilt offsets for pitch and roll, along with an
        angular speed and thrust. We can use this joystick API along with
        feedback from the IMU to virtualize set velocity commands for
        Olympe drones.
        '''
        try:
            ep = common_protocol.Velocity() # Previous error
            max_rotation = self._drone.get_state(MaxRotationSpeedChanged)["max"]
            tp = None # Previous timestamp
            previous_values = None # Previous actuation values

            def clamp(val, mini, maxi):
                return max(mini, min(val, maxi))

            def is_opposite_dir(setpoint, current):
                if setpoint <= 0 and current > 0:
                    return True
                elif setpoint >= 0 and current < 0:
                    return True
                return False

            def update_pid(e, ep, tp, ts, pid_dict):
                P = pid_dict["Kp"] * e
                # Slow down if we are near the setpoint
                if e < 0.5:
                    I = 0.0
                    # Dampen proportional input
                    return P / 2.0, 0.0, 0.0
                I = pid_dict["Ki"] * (ts - tp)
                if e < 0.0:
                    I *= -1
                elif abs(e) <= 0.05 or I * pid_dict["PrevI"] < 0:
                    I = 0.0
                if abs(e) > 0.01:
                    D = pid_dict["Kd"] * (e - ep) / (ts - tp)
                else:
                    D = 0.0

                # For testing Integral component
                I = 0.0
                return P, I, D

            while self._mode == ParrotOlympeDrone.FlightMode.VELOCITY_BODY or \
                    self._mode == ParrotOlympeDrone.FlightMode.VELOCITY_NEU:
                current = common_protocol.Velocity()
                if self._mode == ParrotOlympeDrone.FlightMode.VELOCITY_BODY:
                    current = self._get_velocity_body()
                else:
                    current = self._get_velocity_neu()

                forward_setpoint = self._setpoint.x_vel
                right_setpoint = self._setpoint.y_vel
                up_setpoint = self._setpoint.z_vel
                angular_setpoint = self._setpoint.angular_vel

                forward = 0.0
                right = 0.0
                up = 0.0

                ts = round(time.time() * 1000)

                error = common_protocol.Velocity()
                error.x_vel = forward_setpoint - current.x_vel
                if abs(error.x_vel) < 0.1:
                    error.x_vel = 0
                error.y_vel = right_setpoint - current.y_vel
                if abs(error.y_vel) < 0.1:
                    error.y_vel= 0
                error.z_vel = up_setpoint - current.z_vel
                if abs(error.z_vel) < 0.1:
                    error.z_vel = 0

                # On first loop through, set previous timestamp and error
                # to dummy values.
                if tp is None or (ts - tp) > 1000:
                    tp = ts - 1
                    ep = error

                P, I, D = update_pid(error.x_vel, ep.x_vel, tp, ts, self._forward_pid_values)
                self._forward_pid_values["PrevI"] += I
                forward = P + I + D

                P, I, D = update_pid(error.y_vel, ep.y_vel, tp, ts, self._right_pid_values)
                self._right_pid_values["PrevI"] += I
                right = P + I + D

                P, I, D = update_pid(error.z_vel, ep.z_vel, tp, ts, self._up_pid_values)
                self._up_pid_values["PrevI"] += I
                up = P + I + D

                # Set previous ts and error for next iteration
                tp = ts
                ep = error

                prev_forward = 0
                prev_right = 0
                prev_up = 0
                if previous_values is not None:
                    prev_forward = previous_values.x_vel
                    prev_right = previous_values.y_vel
                    prev_up = previous_values.z_vel

                # Jumpstart braking if we find we are continuing to move in the wrong direction
                new_forward = forward + prev_forward
                forward_round = round(clamp(new_forward, -100, 100))
                forward_round = 0 if is_opposite_dir(forward_setpoint, new_forward) else forward_round
                new_right = right + prev_right
                right_round = round(clamp(new_right, -100, 100))
                right_round = 0 if is_opposite_dir(right_setpoint, new_right) else right_round
                new_up = up + prev_up
                up_round = round(clamp(new_up, -100, 100))
                up_round = 0 if is_opposite_dir(up_setpoint, new_up) else up_round
                ang_round = round(clamp((angular_setpoint / max_rotation) * 100, -100, 100))

                self._drone(PCMD(1, right_round, forward_round, ang_round, up_round, timestampAndSeqNum=0))

                if previous_values is None:
                    previous_values = common_protocol.Velocity()
                # Set the previous values if we are actuating
                previous_values.x_vel = 0 if is_opposite_dir(forward_setpoint, new_forward) \
                        else clamp(new_forward, -100, 100)
                previous_values.y_vel = 0 if is_opposite_dir(right_setpoint, new_right) \
                        else clamp(new_right, -100, 100)
                previous_values.z_vel = 0 if is_opposite_dir(up_setpoint, new_up) \
                        else clamp(new_up, -100, 100)

                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            self._forward_pid_values["PrevI"] = 0.0
            self._right_pid_values["PrevI"] = 0.0
            self._up_pid_values["PrevI"] = 0.0
        except Exception as e:
            logger.error(f"PID iteration failure, reason: {e}")

    ''' ACK methods '''
    def _is_connected(self):
        return self._drone.connection_state()

    def _is_hovering(self):
        return self._drone(FlyingStateChanged(state="hovering", _policy="check"))

    def _is_landed(self):
        return self._drone(FlyingStateChanged(state="landed", _policy="check"))

    def _is_home_set(self, location):
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude
        return self._drone(custom_location(latitude=lat,
            longitude=lon, altitude=alt, _policy='check',
            _float_tol=(1e-07, 1e-09)))

    def _is_home_reached(self):
        return self._drone(state(state=rth_state.state.available, _policy='check',
            _float_tol=(1e-07, 1e-09)))

    def _is_move_by_done(self):
        return self._drone(moveByChanged(status='DONE', _policy='check'))

    def _is_move_to_done(self):
        return self._drone(moveToChanged(status='DONE', _policy='check'))

    def _is_at_target(self, location):
        lat = location.latitude
        lon = location.longitude
        current_location = self._get_global_position()
        if not current_location:
            return False
        dlat = lat - current_location.latitude
        dlon = lon - current_location.longitude
        distance =  math.sqrt((dlat ** 2) + (dlon ** 2)) * 1.113195e5
        return distance <= 1.0

    def _is_rel_altitude_reached(self, target_altitude):
        current_altitude = self._get_altitude_rel()
        diff = abs(current_altitude - target_altitude)
        return diff <= 0.5
    
    def _is_abs_altitude_reached(self, target_altitude):
        current_altitude = self._get_global_position().altitude
        diff = abs(current_altitude - target_altitude)
        return diff <= 0.5

    def _is_global_position_reached(self, location, alt_mode):
        alt = location.altitude
        if self._is_at_target(location):
            if alt_mode == control_protocol.AltitudeMode.ABSOLUTE \
                    and self._is_abs_altitude_reached(alt):
                return True
            elif self._is_rel_altitude_reached(alt):
                return True
        return False

    def _is_velocity_neu_reached(self, velocity):
        north_vel = velocity.x_vel
        east_vel = velocity.y_vel
        up_vel = velocity.z_vel
        # Skip angular velocity since we cannot get it
        vels = self._get_velocity_neu()
        return abs(north_vel - vels.x_vel) <= 0.3 and \
                abs(east_vel - vels.y_vel) <= 0.3 and \
                abs(up_vel - vels.z_vel) <= 0.3

    def _is_velocity_body_reached(self, velocity):
        forward_vel = velocity.x_vel
        right_vel = velocity.y_vel
        up_vel = velocity.z_vel
        # Skip angular velocity since we cannot get it
        vels = self._get_velocity_body()
        return abs(forward_vel - vels.x_vel) <= 0.3 and \
                abs(right_vel - vels.y_vel) <= 0.3 and \
                abs(up_vel - vels.z_vel) <= 0.3

    def _is_heading_reached(self, heading):
        return self._drone(AttitudeChanged(yaw=heading, _policy="check", _float_tol=(1e-3, 1e-1)))

    def _is_gimbal_pose_neu_reached(self, pose):
        return self._drone(attitude(
                pitch_absolute=pose.pitch,
                yaw_absolute=pose.yaw, 
                roll_absolute=pose.roll, 
                _policy="check", 
                _float_tol=(1e-3, 1e-1)
            ))
    
    def _is_gimbal_pose_body_reached(self, pose):
        return self._drone(attitude(
                pitch_relative=pose.pitch,
                yaw_relative=pose.yaw, 
                roll_relative=pose.roll, 
                _policy="check", 
                _float_tol=(1e-3, 1e-1)
            ))

    ''' Helper methods '''
    def _calculate_bearing(self, lat1, lon1, lat2, lon2):
        # Convert latitude and longitude from degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        delta_lon = lon2 - lon1

        # Bearing calculation
        x = math.sin(delta_lon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(delta_lon)

        initial_bearing = math.atan2(x, y)

        # Convert bearing from radians to degrees
        initial_bearing = math.degrees(initial_bearing)

        # Normalize to 0-360 degrees
        converted_bearing = (initial_bearing + 360) % 360

        return converted_bearing

    ''' Stream thread classes '''
    class TelemetryStreamingThread(threading.Thread):
    
        def __init__(self, drone_wrapper, channel):
            threading.Thread.__init__(self)
            self._drone_wrapper = drone_wrapper
            self._channel = channel
            self._frequency = 0
            
        def configure(self, config):
            # Set channel to a new frequency, if it is not zero
            if config.frequency != self._frequency and config.frequency:
                self._frequency = config.frequency
    
        def run(self):
            start_time = time.time()
            while self._frequency:
                try:
                    tel_message = telemetry_protocol.DriverTelemetry()
                    
                    # Stream Info
                    stream_info = telemetry_protocol.TelemetryStreamInfo()
                    stream_info.current_frequency = self._frequency
                    stream_info.max_frequency = 60 # Hz
                    stream_info.uptime.seconds = int(time.time() - start_time)
                    tel_message.telemetry_stream_info.CopyFrom(stream_info)

                    # Vehicle Info
                    vehicle_info = telemetry_protocol.VehicleInfo()
                    # TODO: Change this to be passed in
                    vehicle_info.name = self._drone_wrapper._get_name()
                    vehicle_info.motion_status = \
                        self._drone_wrapper._get_flying_state() 
                    vehicle_info.battery_info.percentage = \
                        self._drone_wrapper._get_battery_percentage()
                    vehicle_info.gps_info.satellites = \
                        self._drone_wrapper._get_satellites()
                    tel_message.vehicle_info.CopyFrom(vehicle_info)

                    # Position Info
                    pos_info = telemetry_protocol.PositionInfo()
                    pos_info.home.CopyFrom(
                        self._drone_wrapper._get_home_position()
                        )
                    pos_info.global_position.CopyFrom(
                        self._drone_wrapper._get_global_position()
                        )
                    pos_info.relative_position.z = \
                        self._drone_wrapper._get_altitude_rel()
                    pos_info.velocity_neu.CopyFrom(
                        self._drone_wrapper._get_velocity_neu()
                        )
                    pos_info.velocity_body.CopyFrom(
                        self._drone_wrapper._get_velocity_body()
                        )
                    # TODO: Need to multiplex based on what type of setpoint it is
                    #pos_info.setpoint_info.setpoint.CopyFrom(
                    #    self._drone_wrapper._setpoint
                    #    )
                    tel_message.position_info.CopyFrom(pos_info)
                    
                    # Gimbal Info
                    tel_message.gimbal_info.CopyFrom(
                        self._drone_wrapper._get_gimbal_info()
                        )

                    # Imaging Sensor Info
                    tel_message.imaging_sensor_info.CopyFrom(
                        self._drone_wrapper._get_imaging_sensor_info()
                        )
                    
                    # Alert Info
                    #tel_message.alert_info.CopyFrom(
                    #    self._drone._get_alert_info()
                    #    )
                    
                    # Send telemetry message over the socket
                    self._channel.send_multipart([b'driver_telemetry', tel_message.SerializeToString()])
                except Exception as e:
                    logger.error(f'Failed to get telemetry, error: {e}')
                # Sleep to maintain transmit frequency (avoid concurrency issues)
                freq = self._frequency
                if freq:
                    time.sleep(1 / freq)
    
        def stop(self):
            self._frequency = 0
    
    class PDRAWImageStreamingThread(threading.Thread):
    
        def __init__(self, drone, drone_wrapper, channel):
            threading.Thread.__init__(self)
            self._channel = channel
            self._drone = drone
            self._drone_wrapper = drone_wrapper
            self._frame_queue = queue.Queue()
            self._current_frame = np.zeros((720, 1280, 3), np.uint8)
    
            self._drone.streaming.set_callbacks(
                raw_cb=self._yuv_frame_callback,
                h264_cb=self._h264_frame_callback,
                start_cb=self._start_callback,
                end_cb=self._end_callback,
                flush_raw_cb=self._flush_callback,
            )
    
        def configure(self, configuration):
            pass
    
        def run(self):
            self.is_running = True
            self._drone.streaming.start()
            frame_id = 0
            
            while self.is_running:
                try:
                    yuv_frame = self._frame_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    cam_message = telemetry_protocol.Frame()
                    frame, frame_shape = self.grab_frame().tobytes(), (720, 1280, 3)
    
                    if frame is None:
                        logger.error('Failed to get video frame')
                        continue
    
                    cam_message.data = frame
                    cam_message.v_res = frame_shape[0]
                    cam_message.h_res = frame_shape[1]
                    cam_message.channels = frame_shape[2]
                    cam_message.id = frame_id
                    
                    # Vehicle Info
                    vehicle_info = telemetry_protocol.VehicleInfo()
                    # TODO: Change this to be passed in
                    vehicle_info.name = self._drone_wrapper._get_name()
                    vehicle_info.motion_status = \
                        self._drone_wrapper._get_flying_state() 
                    vehicle_info.battery_info.percentage = \
                        self._drone_wrapper._get_battery_percentage()
                    vehicle_info.gps_info.satellites = \
                        self._drone_wrapper._get_satellites()
                    cam_message.vehicle_info.CopyFrom(vehicle_info)

                    # Position Info
                    pos_info = telemetry_protocol.PositionInfo()
                    pos_info.home.CopyFrom(
                        self._drone_wrapper._get_home_position()
                        )
                    pos_info.global_position.CopyFrom(
                        self._drone_wrapper._get_global_position()
                        )
                    pos_info.relative_position.z = \
                        self._drone_wrapper._get_altitude_rel()
                    pos_info.velocity_neu.CopyFrom(
                        self._drone_wrapper._get_velocity_neu()
                        )
                    pos_info.velocity_body.CopyFrom(
                        self._drone_wrapper._get_velocity_body()
                        )
                    cam_message.position_info.CopyFrom(pos_info)
                    
                    self._channel.send_multipart([b'driver_imagery', cam_message.SerializeToString()])
                    frame_id = frame_id + 1
                except Exception as e:
                    logger.error(f'Failed to get video frame, error: {e}')
                self._copy_frame(yuv_frame)
                yuv_frame.unref()
    
        def grab_frame(self):
            try:
                frame = self._current_frame.copy()
                return frame
            except Exception as e:
                logger.error(f"Sending blank frame, encountered exception: {e}")
                # Send a blank frame
                return np.zeros((720, 1280, 3), np.uint8)
    
        def _copy_frame(self, yuv_frame):
            info = yuv_frame.info()
    
            height, width = (  # noqa
                info["raw"]["frame"]["info"]["height"],
                info["raw"]["frame"]["info"]["width"],
            )
    
            cv2_cvt_color_flag = {
                olympe.VDEF_I420: cv2.COLOR_YUV2BGR_I420,
                olympe.VDEF_NV12: cv2.COLOR_YUV2BGR_NV12,
            }[yuv_frame.format()]
    
            self._current_frame = cv2.cvtColor(yuv_frame.as_ndarray(), cv2_cvt_color_flag)
    
        '''Olympe callbacks'''
        def _yuv_frame_callback(self, yuv_frame):
            yuv_frame.ref()
            self._frame_queue.put_nowait(yuv_frame)
    
        def _flush_callback(self, stream):
            if stream["vdef_format"] != olympe.VDEF_I420:
                return True
            while not self._frame_queue.empty():
                self._frame_queue.get_nowait().unref()
            return True
    
        def _start_callback(self):
            pass
    
        def _end_callback(self):
            pass
    
        def _h264_frame_callback(self, h264_frame):
            pass
    
        def stop(self):
            self.is_running = False
            # Properly stop the video stream and disconnect
            self._drone.streaming.stop()
