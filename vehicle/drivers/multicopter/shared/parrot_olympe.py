# General imports
import math
import time
import asyncio
import logging
from enum import Enum
import numpy as np
import cv2
import os
# SDK imports (Olympe)
import olympe
from olympe import Drone
from olympe.messages.ardrone3.Piloting import TakeOff, Landing
from olympe.messages.ardrone3.Piloting import PCMD, moveTo, moveBy
from olympe.messages.move import extended_move_to
from olympe.messages.rth import set_custom_location, return_to_home, custom_location, state
import olympe.enums.rth as rth_state
from olympe.messages.common.CommonState import BatteryStateChanged
from olympe.messages.ardrone3.SpeedSettingsState import MaxVerticalSpeedChanged, MaxRotationSpeedChanged
from olympe.messages.ardrone3.PilotingState import AttitudeChanged, GpsLocationChanged, AltitudeChanged, FlyingStateChanged, SpeedChanged, moveToChanged, moveByChanged
from olympe.messages.alarms import alarms
from olympe.messages.ardrone3.GPSState import NumberOfSatelliteChanged
from olympe.messages.gimbal import set_target, attitude
import olympe.enums.gimbal as gimbal_mode
import olympe.enums.move as move_mode
from olympe.messages.common.CalibrationState import MagnetoCalibrationRequiredState
# Interface import
import python_bindings.multicopter_service_pb2_grpc as multicopter_proto
# Protocol imports
import python_bindings.telemetry_pb2 as telemetry_proto
import python_bindings.common_pb2 as common_proto
# Timestamp/Duration import
from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.duration_pb2 import Duration
# Streaming imports
import threading
import queue
# Utility function
from util.utils import generate_response

logger = logging.getLogger(__name__)

# TODO: Remove get type
# Remove streaming from SetHome
# Get streaming threads for telem/imagery to work

class ParrotOlympeDrone(multicopter_proto.MulticopterServicer):

    class FlightMode(Enum):
        LOITER = 'LOITER'
        TAKEOFF_LAND = 'TAKEOFF_LAND'
        VELOCITY_BODY = 'VELOCITY_BODY'
        VELOCITY_ENU = 'VELOCITY_ENU'
        GUIDED_BODY = 'GUIDED_BODY'
        GUIDED_ENU = 'GUIDED_ENU'

    def __init__(self, drone_id, connection_string, **kwargs):
        self._drone_id = drone_id
        self._connection_string = connection_string
        self._kwargs = kwargs
        # Drone flight modes and setpoints
        self._setpoint = common_proto.PositionBody()
        # Set PID values for the drone
        self._forward_pid_values = {}
        self._right_pid_values = {}
        self._up_pid_values = {}
        self._pid_task = None
        self._mode = ParrotOlympeDrone.FlightMode.LOITER

    ''' Interface methods '''
    async def Connect(self, request, context):
        self._drone = Drone(self._connection_string)
        if self._drone.connect():
            yield multicopter_proto.ConnectResponse(
                    response=generate_response(2)
                    )
        else:
            yield multicopter_proto.ConnectResponse(
                    response=generate_response(
                        4, 
                        "Could not connect to vehicle"
                        )
                    )

    async def IsConnected(self, request, context):
        state = self._drone.connection_state()
        return multicopter_proto.IsConnectedResponse(
                response=generate_response(2),
                is_connected=state
                )

    async def Disconnect(self, request, context):
        if self._drone.disconnect():
            return multicopter_proto.DisconnectResponse(
                    response=generate_response(2)
                    )
        else:
            return multicopter_proto.DisconnectResponse(
                    response=generate_response(
                        4,
                        "Could not disconnect from vehicle"
                        )
                    )

    async def TakeOff(self, request, context):
        # Send OK
        yield multicopter_proto.TakeOffResponse(
                response=generate_response(0)
                )

        await self._switch_mode(ParrotOlympeDrone.FlightMode.TAKEOFF_LAND)
        
        # Send the command
        try:
            self._drone(TakeOff())
        except Exception as e:
            yield multicopter_proto.TakeOffResponse(
                    response=generate_response(
                        4,
                        str(e)
                        )
                    )
            return

        # Elevate up to take off altitude 
        while not self._rel_altitude_reached(request.take_off_altitude) \
                and not context.cancelled() \
                and not self._get_altitude_rel() >= request.take_off_altitude:
            try:
                # Elevate at 30% throttle
                self._drone(PCMD(
                    1,
                    0,
                    0,
                    0,
                    30,
                    timestampAndSeqNum=0
                    )).success()
                yield multicopter_proto.TakeOffResponse(
                        response=generate_response(1)
                        )
                await asyncio.sleep(0.01)
            except Exception as e:
                yield multicopter_proto.TakeOffResponse(
                        response=generate_response(
                            4,
                            str(e)
                            )
                        )
                return
        
        try:
            # Halt drone at altitude
            self._drone(PCMD(
                1,
                0,
                0,
                0,
                0,
                timestampAndSeqNum=0
                )).success()
        except Exception as e:
            yield multicopter_proto.TakeOffResponse(
                    response=generate_response(
                        4,
                        str(e)
                        )
                    )
            return
        
        # Send IN_PROGRESS stream
        while not self._is_hovering() and not context.cancelled():
            yield multicopter_proto.TakeOffResponse(
                    response=generate_response(1)
                    )

        await self._switch_mode(ParrotOlympeDrone.FlightMode.LOITER)

        # Send COMPLETED
        yield multicopter_proto.TakeOffResponse(
                response=generate_response(2)
                )

    async def Land(self, request, context):
        # Send OK
        yield multicopter_proto.LandResponse(
                response=generate_response(0)
                )
        
        await self._switch_mode(ParrotOlympeDrone.FlightMode.TAKEOFF_LAND)

        # Send the command
        try:
            self._drone(Landing()).success()
        except Exception as e:
            yield multicopter_proto.LandResponse(
                    response=generate_response(
                        4,
                        str(e)
                        )
                    )
            return

        # Send IN_PROGRESS stream
        while not self._is_landed() and not context.cancelled():
            yield multicopter_proto.LandResponse(
                    response=generate_response(1)
                    )

        await self._switch_mode(ParrotOlympeDrone.FlightMode.LOITER)

        # Send COMPLETED
        yield multicopter_proto.LandResponse(
                response=generate_response(2)
                )

    async def Hold(self, request, context):
        # Send OK
        yield multicopter_proto.HoldResponse(
                response=generate_response(0)
                )
        
        await self._switch_mode(ParrotOlympeDrone.FlightMode.LOITER)

        # Send the command
        try:
            self._drone(PCMD(
                1,
                0,
                0,
                0,
                0,
                timestampAndSeqNum=0
                )).success()
        except Exception as e:
            yield multicopter_proto.HoldResponse(
                    response=generate_response(
                        4,
                        str(e)
                        )
                    )
            return
        
        # Send IN_PROGRESS stream
        while not self._is_hovering() and not context.cancelled():
            yield multicopter_proto.HoldResponse(
                    response=generate_response(1)
                    )

        # Send COMPLETED
        yield multicopter_proto.HoldResponse(
                response=generate_response(2)
                )

    async def Kill(self, request, context):
        # Not supported
        yield multicopter_proto.KillResponse(
                response=generate_response(3)
                )

    async def SetHome(self, request, context):
        # Send OK
        yield multicopter_proto.SetHomeResponse(
                response=generate_response(0)
                )
        
        # Extract home data
        location = request.location
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude

        # Send the command
        try:
            self._drone(set_custom_location(lat, lon, alt)).success()
        except Exception as e:
            yield multicopter_proto.SetHomeResponse(
                    response=generate_response(
                        4,
                        str(e)
                        )
                    )
            return
        
        # Send an IN_PROGRESS stream
        while not self._is_home_set(location) and \
                not context.cancelled():
            yield multicopter_proto.SetHomeResponse(
                    response=generate_response(1)
                    )

        # Send COMPLETED
        yield multicopter_proto.SetHomeResponse(
                response=generate_response(2)
                )

    async def ReturnToHome(self, request, context):
        # Send OK
        yield multicopter_proto.ReturnToHomeResponse(
                response=generate_response(0)
                )
        
        await self._switch_mode(ParrotOlympeDrone.FlightMode.TAKEOFF_LAND)

        # Send the command
        try:
            self._drone(return_to_home()).success()
        except Exception as e:
            yield multicopter_proto.ReturnToHomeResponse(
                    response=generate_response(
                        4,
                        str(e)
                        )
                    )
            return

        await asyncio.sleep(1)

        # Send an IN_PROGRESS stream
        while not self._is_home_reached() and not context.cancelled():
            yield multicopter_proto.ReturnToHomeResponse(
                    response=generate_response(1)
                    )

        await self._switch_mode(ParrotOlympeDrone.FlightMode.LOITER)

        # Send COMPLETED
        yield multicopter_proto.ReturnToHomeResponse(
                response=generate_response(2)
                )

    async def SetGlobalPosition(self, request, context):
        # Send OK
        yield multicopter_proto.SetGlobalPositionResponse(
                response=generate_response(0)
                )

        # Extract location data
        location = request.location
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude
        bearing = location.heading
        alt_mode = request.altitude_mode
        hdg_mode = request.heading_mode
        max_velocity = request.max_velocity
        self._setpoint = location

        # Olympe only accepts relative altitude, so convert absolute to
        # relative altitude in case that is the location mode
        if alt_mode == multicopter_proto.AltitudeMode.ABSOLUTE:
            altitude = alt - self._get_global_position().altitude \
                    + self._get_altitude_rel()
        else:
            altitude = alt
        
        # Set the heading mode and bearing appropriately
        if hdg_mode == multicopter_proto.LocationHeadingMode.TO_TARGET:
            heading_mode = move_mode.orientation_mode.to_target
            bearing = None
        elif hdg_mode == multicopter_proto.LocationHeadingMode.HEADING_START:
            heading_mode = move_mode.orientation_mode.heading_start

        await self._switch_mode(ParrotOlympeDrone.FlightMode.GUIDED)
        
        try:
            # Check if max velocities are provided
            if max_velocity.north_vel or \
                    max_velocity.east_vel or \
                    max_velocity.up_vel or \
                    max_velocity.angular_vel:
                # Set max velocities for transit
                self._drone(
                    extended_move_to(
                        lat,
                        lon,
                        altitude,
                        heading_mode,
                        bearing,
                        max(max_velocity.north_vel, max_velocity.east_vel),
                        max_velocity.up_vel,
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
        except Exception as e:
            yield multicopter_proto.SetGlobalPositionResponse(
                    response=generate_response(
                        4,
                        str(e)
                        )
                    )
            return

        # Sleep momentarily to prevent an early exit
        await asyncio.sleep(1)

        # Send an IN_PROGRESS stream
        while not self._is_move_to_done() and not context.cancelled():
            yield multicopter_proto.SetGlobalPositionResponse(
                    response=generate_response(1)
                    )

        # Check to see if we actually reached our desired position
        if self._is_global_position_reached(location, alt_mode):
            # Send COMPLETED
            yield multicopter_proto.SetGlobalPositionResponse(
                    response=generate_response(2)
                    )
        else:
            # Send FAILED
            yield multicopter_proto.SetGlobalPositionResponse(
                    response=generate_response(
                        4,
                        "Move completed away from target"
                        )
                    )

    async def SetRelativePositionENU(self, request, context):
        # Send NOT_SUPPORTED
        yield multicopter_proto.SetGlobalPositionResponse(
                response=generate_response(3)
                )

    async def SetRelativePositionBody(self, request, context):
        # Send NOT_SUPPORTED
        yield multicopter_proto.SetGlobalPositionResponse(
                response=generate_response(3)
                )

    async def SetVelocityENU(self, request, context):
        # Send OK
        yield multicopter_proto.SetVelocityENUResponse(
                response=generate_response(0)
                )
        
        # Extract velocity data
        self._setpoint = request.velocity

        await self._switch_mode(ParrotOlympeDrone.FlightMode.VELOCITY_ENU)

        # Restart PID task if it isn't already running
        if self._pid_task is None:
            self._pid_task = asyncio.create_task(self._velocity_pid())

        # Send an IN_PROGRESS stream
        while not self._velocity_enu_reached(self._setpoint) \
                and not context.cancelled():
            yield multicopter_proto.SetVelocityENUResponse(
                    response=generate_response(1)
                    )

        # Send COMPLETED
        yield multicopter_proto.SetVelocityENUResponse(
                response=generate_response(2)
                )

    async def SetVelocityBody(self, request, context):
        # Send OK
        yield multicopter_proto.SetVelocityBodyResponse(
                response=generate_response(0)
                )
        
        # Extract velocity data
        self._setpoint = request.velocity

        await self._switch_mode(ParrotOlympeDrone.FlightMode.VELOCITY_BODY)

        # Restart PID task if it isn't already running
        if self._pid_task is None:
            self._pid_task = asyncio.create_task(self._velocity_pid())
        
        # Send an IN_PROGRESS stream
        while not self._velocity_body_reached(self._setpoint) \
                and not context.cancelled():
            yield multicopter_proto.SetVelocityBodyResponse(
                    response=generate_response(1)
                    )

        # Send COMPLETED
        yield multicopter_proto.SetVelocityBodyResponse(
                response=generate_response(2)
                )

    async def SetHeading(self, request, context):
        # Send OK
        yield multicopter_proto.SetHeadingResponse(
                response=generate_response(0)
                )
        
        # Extract location data
        lat = location.latitude
        lon = location.longitude
        bearing = location.bearing
        heading_mode = location.heading_mode

        # Select target based on mode
        if heading_mode == multicopter_proto.HeadingMode.HEADING_START:
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

        try:
            self._drone(moveBy(0.0, 0.0, 0.0, offset)).success()
        except Exception as e:
            yield multicopter_proto.SetHeadingResponse(
                    response=generate_response(
                        4,
                        str(e)
                        )
                    )
            return
        
        # Send an IN_PROGRESS stream
        while not self._is_heading_reached(target) \
                and not context.cancelled() \
                and self._get_compass_state() != 2:
            yield multicopter_proto.SetHeadingResponse(
                    response=generate_response(1)
                    )
        if self._get_compass_state() == 1:
            yield multicopter_proto.SetHeadingResponse(
                    response=generate_response(
                        6,
                        "Weak heading lock, heading may be inaccurate"
                        )
                    )
        elif self._get_compass_state() == 2:
            yield multicopter_proto.SetHeadingResponse(
                    response=generate_response(
                        4,
                        "No heading lock"
                        )
                    )
            return

        # Send COMPLETED
        yield multicopter_proto.SetHeadingResponse(
                response=generate_response(2)
                )

    async def SetGimbalPoseENU(self, request, context):
        # Send OK
        yield multicopter_proto.SetGimbalPoseBodyResponse(
                response=generate_response(0)
                )
        
        # Extract pose data
        gimbal_id = request.gimbal_id
        pose = request.pose
        yaw = pose.yaw
        pitch = pose.pitch
        roll = pose.roll
        control_mode = pose.control_mode

        # Actuate the gimbal depending on mode
        try:
            if control_mode == common_proto.PoseControlMode.POSITION_ABSOLUTE:
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
            elif control_mode == common_proto.PoseControlMode.POSITION_RELATIVE:
                current_gimbal = self._get_gimbal_pose_body(pose.actuator_id)
                target_yaw = current_gimbal['yaw'] + yaw
                target_pitch = current_gimbal['pitch'] + pitch
                target_roll = current_gimbal['roll'] + roll
                
                self._drone(set_target(
                    gimbal_id=gimbal_id,
                    control_mode="position",
                    yaw_frame_of_reference="absolute",
                    yaw=target_yaw,
                    pitch_frame_of_reference="absolute",
                    pitch=target_pitch,
                    roll_frame_of_reference="absolute",
                    roll=target_roll)
                ).success()
            else:
                target_yaw = None
                target_pitch = None
                target_roll = None

                self._drone(set_target(
                    gimbal_id=gimbal_id,
                    control_mode="velocity",
                    yaw_frame_of_reference="absolute",
                    yaw=yaw,
                    pitch_frame_of_reference="absolute",
                    pitch=pitch,
                    roll_frame_of_reference="absolute",
                    roll=roll)
                ).success()
        except Exception as e:
            yield multicopter_proto.SetGimbalPoseBodyResponse(
                    response=generate_response(
                        4,
                        str(e)
                        )
                    )
            return

        if control_mode != common_proto.PoseControlMode.VELOCITY:
            # Send an IN_PROGRESS stream
            while not self._is_gimbal_pose_enu_reached(
                    target_yaw,
                    target_pitch,
                    target_roll
                    ) \
                    and not context.cancelled():
                yield multicopter_proto.SetGimbalPoseBodyResponse(
                        response=generate_response(1)
                        )
        else:
            # We cannot check the velocity of the gimbal from Olympe
                yield multicopter_proto.SetGimbalPoseBodyResponse(
                        response=generate_response(
                            6,
                            "Cannot wait for gimbal velocity to be set"
                            )
                        )
        
        # Send COMPLETED
        yield multicopter_proto.SetGimbalPoseBodyResponse(
                response=generate_response(2)
                )

    async def SetGimbalPoseBody(self, request, context):
        # Send OK
        yield multicopter_proto.SetGimbalPoseBodyResponse(
                response=generate_response(0)
                )
        
        # Extract pose data
        gimbal_id = request.gimbal_id
        pose = request.pose
        yaw = pose.yaw
        pitch = pose.pitch
        roll = pose.roll
        control_mode = pose.control_mode

        # Actuate the gimbal depending on mode
        try:
            if control_mode == common_proto.PoseControlMode.POSITION_ABSOLUTE:
                target_yaw = yaw
                target_pitch = pitch
                target_roll = roll
                
                self._drone(set_target(
                    gimbal_id=gimbal_id,
                    control_mode="position",
                    yaw_frame_of_reference="relative",
                    yaw=yaw,
                    pitch_frame_of_reference="relative",
                    pitch=pitch,
                    roll_frame_of_reference="relative",
                    roll=roll)
                ).success()
            elif control_mode == common_proto.PoseControlMode.POSITION_RELATIVE:
                current_gimbal = self._get_gimbal_pose_body(pose.actuator_id)
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
            else:
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
        except Exception as e:
            yield multicopter_proto.SetGimbalPoseBodyResponse(
                    response=generate_response(
                        4,
                        str(e)
                        )
                    )
            return

        if control_mode != common_proto.PoseControlMode.VELOCITY:
            # Send an IN_PROGRESS stream
            while not self._is_gimbal_pose_body_reached(
                    target_yaw,
                    target_pitch,
                    target_roll
                    ) \
                    and not context.cancelled():
                yield multicopter_proto.SetGimbalPoseBodyResponse(
                        response=generate_response(1)
                        )
        else:
            # We cannot check the velocity of the gimbal from Olympe
                yield multicopter_proto.SetGimbalPoseBodyResponse(
                        response=generate_response(
                            6,
                            "Cannot wait for gimbal velocity to be set"
                            )
                        )
        
        # Send COMPLETED
        yield multicopter_proto.SetGimbalPoseBodyResponse(
                response=generate_response(2)
                )

    async def ConfigureImagingSensorStream(self, request, context):
        
    async def ConfigureTelemetryStream(self, request, context):

    async def stream_video(self, cam_sock, rate_hz):
        logger.info('Starting camera stream')
        self._start_streaming()
        frame_id = 0
        while await self.is_connected():
            try:
                cam_message = data_protocol.Frame()
                frame, frame_shape = await self._get_video_frame()

                if frame is None:
                    logger.error('Failed to get video frame')
                    continue

                cam_message.data = frame
                cam_message.height = frame_shape[0]
                cam_message.width = frame_shape[1]
                cam_message.channels = frame_shape[2]
                cam_message.id = frame_id
                cam_sock.send(cam_message.SerializeToString())
                frame_id = frame_id + 1
            except Exception as e:
                logger.error(f'Failed to get video frame, error: {e}')
            await asyncio.sleep(0.1)
        self._stop_streaming()
        logger.info("Camera stream ended, disconnected from drone")

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
        loc = self._drone.get_state(custom_location)
        if not loc:
            loc = self._drone.get_state(takeoff_location)
        location = common_proto.Location()
        location.latitude = loc["latitude"]
        location.longitude = loc["longitude"]
        return location

    def _get_global_position(self):
        loc = self._drone.get_state(GpsLocationChanged)
        location = common_proto.Location()
        location.latitude = loc["latitude"]
        location.longitude = loc["longitude"]
        location.altitude = loc["altitude"]
        location.heading = self._drone._get_heading()
        return location

    def _get_gps_state(self):
        state = self._drone.get_state(GpsFixStateChanged)
        sats = self._drone._get_satellites()
        if not state["fixed"]:
            return telemetry_proto.GPSWarning.NO_FIX
        elif sats < 10:
            return telemetry_proto.GPSWarning.WEAK_SIGNAL
        else:
            return telemetry_proto.GPSWarning.NO_GPS_WARNING

    def _get_altitude_rel(self):
        return self._drone.get_state(AltitudeChanged)["altitude"]

    def _get_magnetometer_state(self):
        mag = self._drone(alarms(type=3, status=1, _policy='check'))
        if mag:
            return telemetry_proto.MagnetometerWarning.PERTURBATION
        else:
            return telemetry_proto.MagnetometerWarning.NO_MAGNETOMETER_WARNING

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

    def _get_velocity_enu(self):
        ned = self._drone.get_state(SpeedChanged)
        velocity = common_proto.VelocityENU()
        velocity.north = ned["speedX"]
        velocity.east = ned["speedY"]
        velocity.up = ned["speedZ"] * -1
        return velocity

    def _get_velocity_body(self):
        enu = self._get_velocity_enu()
        vec = np.array([enu["north"], enu["east"]], dtype=float)
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

        velocity = common_proto.VelocityBody()
        velocity.forward = np.dot(vec, vecf) * -1
        velocity.right = np.dot(vec, vecr) * -1
        velocity.up = enu["up"]
        return velocity

    def _get_gimbal_info(self):
        # TODO: Must be implemented for each drone
        return telemetry_proto.GimbalInfo()

    def _get_gimbal_pose_body(self, gimbal_id):
        pose = common_proto.Pose()
        pose.yaw = \
            self._drone.get_state(attitude)[gimbal_id]["yaw_relative"]
        pose.pitch = \
            self._drone.get_state(attitude)[gimbal_id]["pitch_relative"]
        pose.roll = \
            self._drone.get_state(attitude)[gimbal_id]["roll_relative"]
        return pose
    
    def _get_gimbal_pose_enu(self, gimbal_id):
        pose = common_proto.Pose()
        pose.yaw = \
            self._drone.get_state(attitude)[gimbal_id]["yaw_absolute"]
        pose.pitch = \
            self._drone.get_state(attitude)[gimbal_id]["pitch_absolute"]
        pose.roll = \
            self._drone.get_state(attitude)[gimbal_id]["roll_absolute"]
        return pose

    def _get_imaging_sensor_info(self):
        # TODO: Must be implemented for each drone
        return telemetry_proto.ImagingSensorInfo()

    def _get_compass_state(self):
        state = self._drone.get_state(HeadingLockedStateChanged)["state"]
        if state == "OK":
            return telemetry.CompassWarning.NO_COMPASS_WARNING
        elif state == "WARNING":
            return telemetry.CompassWarning.WEAK_HEADING_LOCK
        else:
            return telemetry.CompassWarning.NO_HEADING_LOCK

    def _get_alert_info(self):
        alert_info = telemetry_info.AlertInfo()

        battery = self._drone._get_battery_percentage()
        gps = self._drone._get_gps_state()
        magnetometer = self._drone._get_magnetometer_state()
        compass = self._drone._get_compass_state()

        if battery <= 30:
            alert_info.battery_warning = \
                telemetry_info.BatteryWarning.LOW
        elif battery <= 15:
            alert_info.battery_warning = \
                telemetry_info.BatteryWarning.CRITICAL

        alert_info.gps_warning = gps
        alert_info.magnetometer_warning = magnetometer
        alert_info.compass_warning = compass

        return alert_info

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
            ep = common_proto.VelocityBody() # Previous error
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
                    self._mode == ParrotOlympeDrone.FlightMode.VELOCITY_ENU:
                current = common_proto.VelocityBody()
                if self._mode == ParrotOlympeDrone.FlightMode.VELOCITY_BODY:
                    current = self._get_velocity_body()
                    forward_setpoint = self._setpoint.forward_vel
                    right_setpoint = self._setpoint.right_vel
                    up_setpoint = self._setpoint.up_vel
                    angular_setpoint = self._setpoint.angular_vel
                else:
                    current = self._get_velocity_enu()
                    forward_setpoint = self._setpoint.north_vel
                    right_setpoint = self._setpoint.east_vel
                    up_setpoint = self._setpoint.up_vel
                    angular_setpoint = self._setpoint.angular_vel

                forward = 0.0
                right = 0.0
                up = 0.0

                ts = round(time.time() * 1000)

                error = common_proto.VelocityBody()
                error.forward = forward_setpoint - current.forward
                if abs(error.forward) < 0.1:
                    error.forward = 0
                error.right = right_setpoint - current.right
                if abs(error.right) < 0.1:
                    error.right = 0
                error.up = up_setpoint - current.up
                if abs(error.up) < 0.1:
                    error.up = 0

                # On first loop through, set previous timestamp and error
                # to dummy values.
                if tp is None or (ts - tp) > 1000:
                    tp = ts - 1
                    ep = error

                P, I, D = update_pid(error.forward, ep.forward, tp, ts, self._forward_pid_values)
                self._forward_pid_values["PrevI"] += I
                forward = P + I + D

                P, I, D = update_pid(error.right, ep.right, tp, ts, self._right_pid_values)
                self._right_pid_values["PrevI"] += I
                right = P + I + D

                P, I, D = update_pid(error.up, ep.up, tp, ts, self._up_pid_values)
                self._up_pid_values["PrevI"] += I
                up = P + I + D

                # Set previous ts and error for next iteration
                tp = ts
                ep = error

                prev_forward = 0
                prev_right = 0
                prev_up = 0
                if previous_values is not None:
                    prev_forward = previous_values.forward
                    prev_right = previous_values.right
                    prev_up = previous_values.up

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
                    previous_values = common_proto.VelocityBody()
                # Set the previous values if we are actuating
                previous_values.forward = 0 if is_opposite_dir(forward_setpoint, new_forward) \
                        else clamp(new_forward, -100, 100)
                previous_values.right = 0 if is_opposite_dir(right_setpoint, new_right) \
                        else clamp(new_right, -100, 100)
                previous_values.up = 0 if is_opposite_dir(up_setpoint, new_up) \
                        else clamp(new_up, -100, 100)

                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            self._forward_pid_values["PrevI"] = 0.0
            self._right_pid_values["PrevI"] = 0.0
            self._up_pid_values["PrevI"] = 0.0
        except Exception as e:
            logger.error(f"PID iteration failure, reason: {e}")

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

    ''' ACK methods '''
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
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude
        if self._is_at_target(lat, lon):
            if alt_mode == multicopter_proto.AltitudeMode.ABSOLUTE \
                    and self._is_abs_altitude_reached(alt):
                return True
            elif self._is_rel_altitude_reached(alt):
                return True
        return False

    def _is_velocity_enu_reached(self, velocity):
        north_vel = velocity.north_vel
        east_vel = velocity.east_vel
        up_vel = velocity.up_vel
        # Skip angular velocity since we cannot get it
        vels = self._get_velocity_enu()
        return abs(north_vel - vels.north) <= 0.3 and \
                abs(east_vel - vels.east) <= 0.3 and \
                abs(up_vel - vels.up) <= 0.3

    def _is_velocity_body_reached(self, velocity):
        forward_vel = velocity.forward_vel
        right_vel = velocity.right_vel
        up_vel = velocity.up_vel
        # Skip angular velocity since we cannot get it
        vels = self._get_velocity_body()
        return abs(forward_vel - vels.forward) <= 0.3 and \
                abs(right_vel - vels.right) <= 0.3 and \
                abs(up_vel - vels.up) <= 0.3

    def _is_heading_reached(self, heading):
        return self._drone(AttitudeChanged(yaw=heading, _policy="check", _float_tol=(1e-3, 1e-1)))

    def _is_gimbal_pose_enu_reached(self, pose):
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

    async def _wait_for_condition(self, condition_fn, timeout=None, interval=0.5):
        start_time = time.time()
        while True:
            try:
                if condition_fn():
                    return True
            except Exception as e:
                logger.error(f"Error while waiting for condition, {e}")
            if timeout is not None and time.time() - start_time > timeout:
                return False
            await asyncio.sleep(interval)

    ''' Streaming methods '''
    def _start_streaming(self):
        if "stream" in self._kwargs and self._kwargs["stream"] == "ffmpeg":
            logger.info("Using FFmpeg for streaming")
            self._streaming_thread = FFMPEGStreamingThread(self._drone, self.ip)
        else:
            logger.info("Using PDrAW for streaming")
            self._streaming_thread = PDRAWStreamingThread(self._drone)

        self._streaming_thread.start()

    async def _get_video_frame(self):
        if self._streaming_thread:
            return self._streaming_thread.grab_frame().tobytes(), (720, 1280, 3)

    def _stop_streaming(self):
        self._streaming_thread.stop()

    ''' Stream thread classes '''
    class TelemetryStreamingThread(threading.Thread):
    
        def __init__(self, drone, config):
            self._drone = drone
            self._socket = zmq.Context().socket(zmq.PUB)
            self._channel = ""
            self._frequency = 0
            self.configure(config)
    
        def configure(self, config):
            # Bind to a new channel, if necessary
            if config.channel != self._channel and config.channel != "":
                self._socket.bind(config.channel)
                self._channel = config.channel
            # Set channel to a new frequency, if it is not zero
            if config.frequency != self._frequency and config.frequency:
                self._frequency = config.frequency
    
        def run(self):
            start_time = time.time()
            while self._frequency:
                try:
                    tel_message = telemetry_proto.DriverTelemetry()
                    
                    # Stream Info
                    stream_info = telemetry_proto.TelemetryStreamInfo()
                    stream_info.current_frequency = self._frequency
                    stream_info.max_frequency = 60 # Hz
                    stream_info.uptime = Duration(seconds=time.time() - start_time)
                    tel_message.stream_info = stream_info

                    # Vehicle Info
                    vehicle_info = telemetry_proto.VehicleInfo()
                    vehicle_info.name = self._name
                    vehicle_info.model = self._model
                    vehicle_info.manufacturer = self._manufacturer
                    vehicle_info.motion_status = \
                        self._drone._get_flying_state() 
                    vehicle_info.battery_info.percentage = \
                        self._drone._get_battery_percentage()
                    vehicle_info.gps_info.satellites = \
                        self._drone._get_satellites()
                    tel_message.vehicle_info = vehicle_info

                    # Position Info
                    pos_info = telemetry_proto.PositionInfo()
                    pos_info.home = \
                            self._drone._get_home_position()
                    pos_info.global_position = \
                            self._drone._get_global_position()
                    pos_info.relative_position.up = \
                        self._drone._get_altitude_rel()
                    pos_info.velocity_enu = \
                            self._drone._get_velocity_enu()
                    pos_info.velocity_body = \
                            self._drone._get_velocity_body()
                    pos_info.setpoint_info.setpoint = \
                        self._setpoint
                    tel_message.position_info = pos_info
                    
                    # Gimbal Info
                    tel_message.gimbal_info = \
                        self._drone._get_gimbal_info()

                    # Imaging Sensor Info
                    tel_message.imaging_sensor_info = \
                        self._drone._get_imaging_sensor_info()
                    
                    # Alert Info
                    tel_message.alert_info = \
                        self._drone._get_alert_info()
                    
                    # Send telemetry message over the socket
                    self._socket.send(tel_message.SerializeToString())
                except Exception as e:
                    logger.error(f'Failed to get telemetry, error: {e}')
                # Sleep to maintain transmit frequency (avoid concurrency issues)
                freq = self._frequency
                if freq:
                    time.sleep(1 / freq)
    
        def stop(self):
            self._frequency = 0
    
    class PDRAWImageStreamingThread(threading.Thread):
    
        def __init__(self, drone, channel):
            threading.Thread.__init__(self)
    
            self._drone = drone
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
    
            while self.is_running:
                try:
                    yuv_frame = self._frame_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                try:
                    cam_message = data_protocol.Frame()
                    frame, frame_shape = await self._get_video_frame()
    
                    if frame is None:
                        logger.error('Failed to get video frame')
                        continue
    
                    cam_message.data = frame
                    cam_message.height = frame_shape[0]
                    cam_message.width = frame_shape[1]
                    cam_message.channels = frame_shape[2]
                    cam_message.id = frame_id
                    cam_sock.send(cam_message.SerializeToString())
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
    
    
    class FFMPEGImageStreamingThread(threading.Thread):
    
        def __init__(self, ip, channel):
            threading.Thread.__init__(self)
    
            logger.info(f"Using opencv-python version {cv2.__version__}")
    
            self._current_frame = None
            self.ip = ip
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"
            self.is_running = False
    
        def configure(self, configuration):
            pass
    
        def run(self):
            while not self.is_running:
                self._cap = cv2.VideoCapture(f"rtsp://{self.ip}/live", cv2.CAP_FFMPEG, (cv2.CAP_PROP_N_THREADS, 1))
                self.is_running = True
                while self.is_running:
                    try:
                        ret, self._current_frame = self._cap.read()
                        if not ret:
                            logger.error(f"No frame received from cap, restarting")
                            self.is_running = False
                    except Exception as e:
                        logger.error(f"Frame could not be read, reason: {e}")
                        self.is_running = False
                self._cap.release()
    
        def grab_frame(self):
            try:
                frame = self._current_frame.copy()
                return frame
            except Exception as e:
                logger.error(f"Grab frame failed, reason: {e}")
                # Send a blank frame
                return np.zeros((720, 1280, 3), np.uint8)
    
        def stop(self):
            self.is_running = False
    
