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
from olympe.messages.ardrone3.GPSState import NumberOfSatelliteChanged
from olympe.messages.gimbal import set_target, attitude
import olympe.enums.gimbal as gimbal_mode
import olympe.enums.move as move_mode
from olympe.messages.common.CalibrationState import MagnetoCalibrationRequiredState
# Interface import
from python.multicopter_pb2_grpc as multicopter_proto
# Protocol imports
import python.telemetry_pb2 as telemetry_proto
import python.common_pb2 as common_proto
# Timestamp/Duration import
from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.duration_pb2 import Duration
# Streaming imports
import threading
import queue

logger = logging.getLogger(__name__)

class ParrotOlympeDrone(multicopter_proto.MulticopterServicer):

    class FlightMode(Enum):
        LOITER = 'LOITER'
        TAKEOFF_LAND = 'TAKEOFF_LAND'
        VELOCITY_BODY = 'VELOCITY_BODY'
        VELOCITY_ENU = 'VELOCITY_ENU'
        GUIDED_BODY = 'GUIDED_BODY'
        GUIDED_ENU = 'GUIDED_ENU'

    @staticmethod
    def generate_response(resp_type, resp_string=""):
        return common_proto.Response(
                status=resp_type,
                response_string=resp_string,
                timestamp=Timestamp().GetCurrentTime()
                )

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
    async def GetType(self, request, context):
        return multicopter_proto.GetTypeResponse(
                response=ParrotOlympeDrone.generate_response(2),
                type="Parrot Olympe Drone"
                )

    async def Connect(self, request, context):
        # Send OK
        yield multicopter_proto.ConnectResponse(
                response=ParrotOlympeDrone.generate_response(0)
                )

        self._drone = Drone(self._connection_string)
        if self._drone.connect():
            return multicopter_proto.ConnectResponse(
                    response=ParrotOlympeDrone.generate_response(2)
                    )
        else:
            return multicopter_proto.ConnectResponse(
                    response=ParrotOlympeDrone.generate_response(
                        4, 
                        "Could not connect to vehicle"
                        )
                    )

    async def IsConnected(self, request, context):
        state = self._drone.connection_state()
        return multicopter_proto.IsConnectedResponse(
                response=ParrotOlympeDrone.generate_response(2),
                is_connected=state
                )

    async def Disconnect(self, request, context):
        if self._drone.disconnect():
            return multicopter_proto.DisconnectResponse(
                    response=ParrotOlympeDrone.generate_response(2)
                    )
        else:
            return multicopter_proto.DisconnectResponse(
                    response=ParrotOlympeDrone.generate_response(
                        4,
                        "Could not disconnect from vehicle"
                        )
                    )

    async def TakeOff(self, request, context):
        # Send OK
        yield multicopter_proto.TakeOffResponse(
                response=ParrotOlympeDrone.generate_response(0)
                )

        await self._switch_mode(ParrotOlympeDrone.FlightMode.TAKEOFF_LAND)
        
        # Send the command
        try:
            self._drone(TakeOff())
        except Exception as e:
            return multicopter_proto.TakeOffResponse(
                    response=ParrotOlympeDrone.generate_response(
                        4,
                        str(e)
                        )
                    )

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
                        response=ParrotOlympeDrone.generate_response(1)
                        )
                await asyncio.sleep(0.01)
            except Exception as e:
                return multicopter_proto.TakeOffResponse(
                        response=ParrotOlympeDrone.generate_response(
                            4,
                            str(e)
                            )
                        )
        
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
            return multicopter_proto.TakeOffResponse(
                    response=ParrotOlympeDrone.generate_response(
                        4,
                        str(e)
                        )
                    )
        
        # Send IN_PROGRESS stream
        while not self._is_hovering() and not context.cancelled():
            yield multicopter_proto.TakeOffResponse(
                    response=ParrotOlympeDrone.generate_response(1)
                    )

        await self._switch_mode(ParrotOlympeDrone.FlightMode.LOITER)

        # Send COMPLETED
        return multicopter_proto.TakeOffResponse(
                response=ParrotOlympeDrone.generate_response(2)
                )

    async def Land(self, request, context):
        # Send OK
        yield multicopter_proto.LandResponse(
                response=ParrotOlympeDrone.generate_response(0)
                )
        
        await self._switch_mode(ParrotOlympeDrone.FlightMode.TAKEOFF_LAND)

        # Send the command
        try:
            self._drone(Landing()).success()
        except Exception as e:
            return multicopter_proto.LandResponse(
                    response=ParrotOlympeDrone.generate_response(
                        4,
                        str(e)
                        )

        # Send IN_PROGRESS stream
        while not self._is_landed() and not context.cancelled():
            yield multicopter_proto.LandResponse(
                    response=ParrotOlympeDrone.generate_response(1)
                    )

        await self._switch_mode(ParrotOlympeDrone.FlightMode.LOITER)

        # Send COMPLETED
        return multicopter_proto.LandResponse(
                response=ParrotOlympeDrone.generate_response(2)
                )

    async def Hold(self, request, context):
        # Send OK
        yield multicopter_proto.HoldResponse(
                response=ParrotOlympeDrone.generate_response(0)
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
            return multicopter_proto.HoldResponse(
                    response=ParrotOlympeDrone.generate_response(
                        4,
                        str(e)
                        )
        
        # Send IN_PROGRESS stream
        while not self._is_hovering() and not context.cancelled()
            yield multicopter_proto.HoldResponse(
                    response=ParrotOlympeDrone.generate_response(1)
                    )

        # Send COMPLETED
        return multicopter_proto.HoldResponse(
                response=ParrotOlympeDrone.generate_response(2)
                )

    async def Kill(self, request, context):
        # Not supported
        return multicopter_proto.KillResponse(
                response=ParrotOlympeDrone.generate_response(3)
                )

    async def SetHome(self, request, context):
        # Send OK
        yield multicopter_proto.SetHomeResponse(
                response=ParrotOlympeDrone.generate_response(0)
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
            return multicopter_proto.SetHomeResponse(
                    response=ParrotOlympeDrone.generate_response(
                        4,
                        str(e)
                        )
                    )
        
        # Send an IN_PROGRESS stream
        while not self._is_home_set(location) and \
                not context.cancelled():
            yield multicopter_proto.SetHomeResponse(
                    response=ParrotOlympeDrone.generate_response(1)
                    )

        # Send COMPLETED
        return multicopter_proto.SetHomeResponse(
                response=ParrotOlympeDrone.generate_response(2)
                )

    async def ReturnToHome(self, request, context):
        # Send OK
        yield multicopter_proto.ReturnToHomeResponse(
                response=ParrotOlympeDrone.generate_response(0)
                )
        
        await self._switch_mode(ParrotOlympeDrone.FlightMode.TAKEOFF_LAND)

        # Send the command
        try:
            self._drone(return_to_home()).success()
        except Exception as e:
            return multicopter_proto.ReturnToHomeResponse(
                    response=ParrotOlympeDrone.generate_response(
                        4,
                        str(e)
                        )
                    )

        await asyncio.sleep(1)

        # Send an IN_PROGRESS stream
        while not self._is_home_reached() and not context.cancelled():
            yield multicopter_proto.ReturnToHomeResponse(
                    response=ParrotOlympeDrone.generate_response(1)
                    )

        await self._switch_mode(ParrotOlympeDrone.FlightMode.LOITER)

        # Send COMPLETED
        return multicopter_proto.ReturnToHomeResponse(
                response=ParrotOlympeDrone.generate_response(2)
                )

    async def SetGlobalPosition(self, request, context):
        # Send OK
        yield multicopter_proto.SetGlobalPositionResponse(
                response=ParrotOlympeDrone.generate_response(0)
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
            altitude = alt - self._get_global_position()["altitude"] \
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
            return multicopter_proto.SetGlobalPositionResponse(
                    response=ParrotOlympeDrone.generate_response(
                        4,
                        str(e)
                        )
                    )

        # Sleep momentarily to prevent an early exit
        await asyncio.sleep(1)

        # Send an IN_PROGRESS stream
        while not self._is_move_to_done() and not context.cancelled():
            yield multicopter_proto.SetGlobalPositionResponse(
                    response=ParrotOlympeDrone.generate_response(1)
                    )

        # Check to see if we actually reached our desired position
        if self._is_global_position_reached(location, alt_mode):
            # Send COMPLETED
            return multicopter_proto.SetGlobalPositionResponse(
                    response=ParrotOlympeDrone.generate_response(2)
                    )
        else:
            # Send FAILED
            return multicopter_proto.SetGlobalPositionResponse(
                    response=ParrotOlympeDrone.generate_response(
                        4,
                        "Move completed away from target"
                        )
                    )

    async def SetRelativePositionENU(self, request, context):
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def SetRelativePositionBody(self, request, context):
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def SetVelocityENU(self, request, context):
        # Send OK
        yield multicopter_proto.SetVelocityENUResponse(
                response=ParrotOlympeDrone.generate_response(0)
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
                    response=ParrotOlympeDrone.generate_response(1)
                    )

        # Send COMPLETED
        return multicopter_proto.SetVelocityENUResponse(
                response=ParrotOlympeDrone.generate_response(2)
                )

    async def SetVelocityBody(self, request, context):
        # Send OK
        yield multicopter_proto.SetVelocityBodyResponse(
                response=ParrotOlympeDrone.generate_response(0)
                )
        
        # Extract velocity data
        self._setpoint = request.velocity

        await self._switch_mode(ParrotOlympeDrone.FlightMode.VELOCITY_BODY)

        # Restart PID task if it isn't already running
        if self._pid_task is None:
            self._pid_task = asyncio.create_task(self._velocity_pid())

        return common_protocol.ResponseStatus.COMPLETED

    async def SetHeading(self, request, context):
        lat = location.latitude
        lon = location.longitude
        bearing = location.bearing
        heading_mode = location.heading_mode

        if heading_mode == common_protocol.LocationHeadingMode.HEADING_START:
            target = bearing
        else:
            global_position = self._get_global_position()
            target = self._calculate_bearing(
                    global_position["latitude"],
                    global_position["longitude"],
                    lat,
                    lon
                    )
        offset = math.radians(heading - target)

        try:
            self._drone(moveBy(0.0, 0.0, 0.0, offset)).success()
        except:
            return common_protocol.ResponseStatus.FAILED

        result = await self._wait_for_condition(
            lambda: self._is_heading_reached(target),
            interval=0.5
        )

        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def SetGimbalPoseENU(self, request, context):
        pass

    async def SetGimbalPoseBody(self, request, context):
        yaw = pose.yaw
        pitch = pose.pitch
        roll = pose.roll
        control_mode = pose.control_mode

        # Actuate the gimbal
        try:
            if control_mode == common_protocol.PoseControlMode.POSITION_ABSOLUTE:
                target_yaw = yaw
                target_pitch = pitch
                target_roll = roll
                
                self._drone(set_target(
                    gimbal_id=0,
                    control_mode="position",
                    yaw_frame_of_reference="relative",
                    yaw=yaw,
                    pitch_frame_of_reference="relative",
                    pitch=pitch,
                    roll_frame_of_reference="relative",
                    roll=roll)
                ).success()
            elif control_mode == common_protocol.PoseControlMode.POSITION_RELATIVE:
                current_gimbal = await self._get_gimbal_pose_body(pose.actuator_id)
                target_yaw = current_gimbal['yaw'] + yaw
                target_pitch = current_gimbal['pitch'] + pitch
                target_roll = current_gimbal['roll'] + roll
                
                self._drone(set_target(
                    gimbal_id=0,
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
                    gimbal_id=0,
                    control_mode="velocity",
                    yaw_frame_of_reference="relative",
                    yaw=yaw,
                    pitch_frame_of_reference="relative",
                    pitch=pitch,
                    roll_frame_of_reference="relative",
                    roll=roll)
                ).success()
        except:
            return common_protocol.ResponseStatus.FAILED

        if control_mode != common_protocol.PoseControlMode.VELOCITY:
            result = await self._wait_for_condition(
                lambda: self._is_gimbal_pose_reached(
                    target_yaw,
                    target_pitch, 
                    target_roll
                ),
                timeout=10,
                interval=0.5
            )
        else:
            # We cannot check the velocity of the gimbal from Olympe
            result = True

        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def stream_telemetry(self, tel_sock, rate_hz):
        logger.info('Starting telemetry stream')
        # Wait a second to avoid contention issues
        await asyncio.sleep(1)
        while await self.is_connected():
            try:
                tel_message = data_protocol.Telemetry()
                tel_message.drone_name = self._get_name()
                tel_message.battery = self._get_battery_percentage()
                tel_message.satellites = self._get_satellites()
                tel_message.global_position.latitude = \
                    self._get_global_position()["latitude"]
                tel_message.global_position.longitude = \
                    self._get_global_position()["longitude"]
                tel_message.global_position.altitude = \
                    self._get_global_position()["altitude"]
                tel_message.relative_position.up = \
                    self._get_altitude_rel()
                tel_message.global_position.heading = self._get_heading()
                tel_message.velocity_enu.north_vel = \
                    self._get_velocity_enu()["north"]
                tel_message.velocity_enu.east_vel = \
                    self._get_velocity_enu()["east"]
                tel_message.velocity_enu.up_vel = \
                    self._get_velocity_enu()["up"]
                tel_message.velocity_body.forward_vel = \
                    self._get_velocity_body()["forward"]
                tel_message.velocity_body.right_vel = \
                    self._get_velocity_body()["right"]
                tel_message.velocity_body.up_vel = \
                    self._get_velocity_body()["up"]
                gimbal = await self._get_gimbal_pose_body(0)
                tel_message.gimbal_pose.pitch = gimbal["pitch"]
                tel_message.gimbal_pose.roll = gimbal["roll"]
                tel_message.gimbal_pose.yaw = gimbal["yaw"]
                batt = tel_message.battery
                
                # Warnings
                if batt <= 15:
                    tel_message.alerts.battery_warning = \
                        common_protocol.BatteryWarning.CRITICAL
                elif batt <= 30:
                    tel_message.alerts.battery_warning = \
                        common_protocol.BatteryWarning.LOW
                mag = self._get_magnetometer()
                if mag == 2:
                    tel_message.alerts.magnetometer_warning = \
                        common_protocol.MagnetometerWarning.RECOMMENDED
                elif mag == 1:
                    tel_message.alerts.magnetometer_warning = \
                        common_protocol.MagnetometerWarning.REQUIRED
                sats = tel_message.satellites
                if sats == 0:
                    tel_message.alerts.gps_warning = \
                        common_protocol.GPSWarning.NO_SIGNAL
                elif sats <= 10:
                    tel_message.alerts.gps_warning = \
                        common_protocol.GPSWarning.WEAK

                tel_sock.send(tel_message.SerializeToString())
            except Exception as e:
                logger.error(f'Failed to get telemetry, error: {e}')
            await asyncio.sleep(0.1)

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

    def _get_global_position(self):
        try:
            return self._drone.get_state(GpsLocationChanged)
        except:
            return None

    def _get_altitude_rel(self):
        return self._drone.get_state(AltitudeChanged)["altitude"]

    def _get_attitude(self):
        att = self._drone.get_state(AttitudeChanged)
        rad_to_deg = 180 / math.pi
        return {
            "roll": att["roll"] * rad_to_deg,
            "pitch": att["pitch"] * rad_to_deg,
            "yaw": att["yaw"] * rad_to_deg
        }

    def _get_magnetometer(self):
        # Returns 0 if good, 1 if needs calibration, 2 if perturbed
        return self._drone.get_state(MagnetoCalibrationRequiredState)["required"]

    def _get_battery_percentage(self):
        return self._drone.get_state(BatteryStateChanged)["percent"]

    def _get_satellites(self):
        try:
            sats = self._drone.get_state(NumberOfSatelliteChanged)["numberOfSatellite"]
            return sats if sats else 0
        except:
            return 0

    def _get_heading(self):
        diff = 90 - math.degrees(self._drone.get_state(AttitudeChanged)["yaw"])
        if diff > 180:
            return diff - 360
        elif diff < -180
            return diff + 360

    def _get_velocity_enu(self):
        ned = self._drone.get_state(SpeedChanged)
        return {"north": ned["speedX"], "east": ned["speedY"], "up": ned["speedZ"] * -1}

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

        res = {
            "forward": np.dot(vec, vecf) * -1,
            "right": np.dot(vec, vecr) * -1,
            "up": enu["up"],
        }
        return res

    def _get_gimbal_pose_body(self, gimbal_id):
        return {
            "yaw": self._drone.get_state(attitude)[gimbal_id]["yaw_relative"],
            "pitch": self._drone.get_state(attitude)[gimbal_id]["pitch_relative"],
            "roll": self._drone.get_state(attitude)[gimbal_id]["roll_relative"]
        }

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
            ep = {"forward": 0.0, "right": 0.0, "up": 0.0} # Previous error
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
                current = {"forward": 0.0, "right": 0.0, "up": 0.0}
                if self._mode == ParrotOlympeDrone.FlightMode.VELOCITY_BODY:
                    vel_body = self._get_velocity_body()
                    current["forward"] = vel_body["forward"]
                    current["right"] = vel_body["right"]
                    current["up"] = vel_body["up"]
                    forward_setpoint = self._setpoint.forward_vel
                    right_setpoint = self._setpoint.right_vel
                    up_setpoint = self._setpoint.up_vel
                    angular_setpoint = self._setpoint.angular_vel
                else:
                    vel_enu = self._get_velocity_enu()
                    current["forward"] = vel_enu["north"]
                    current["right"] = vel_enu["east"]
                    current["up"] = vel_enu["up"]
                    forward_setpoint = self._setpoint.north_vel
                    right_setpoint = self._setpoint.east_vel
                    up_setpoint = self._setpoint.up_vel
                    angular_setpoint = self._setpoint.angular_vel

                forward = 0.0
                right = 0.0
                up = 0.0

                ts = round(time.time() * 1000)

                error = {}
                error["forward"] = forward_setpoint - current["forward"]
                if abs(error["forward"]) < 0.1:
                    error["forward"] = 0
                error["right"] = right_setpoint - current["right"]
                if abs(error["right"]) < 0.1:
                    error["right"] = 0
                error["up"] = up_setpoint - current["up"]
                if abs(error["up"]) < 0.1:
                    error["up"] = 0

                # On first loop through, set previous timestamp and error
                # to dummy values.
                if tp is None or (ts - tp) > 1000:
                    tp = ts - 1
                    ep = error

                P, I, D = update_pid(error["forward"], ep["forward"], tp, ts, self._forward_pid_values)
                self._forward_pid_values["PrevI"] += I
                forward = P + I + D

                P, I, D = update_pid(error["right"], ep["right"], tp, ts, self._right_pid_values)
                self._right_pid_values["PrevI"] += I
                right = P + I + D

                P, I, D = update_pid(error["up"], ep["up"], tp, ts, self._up_pid_values)
                self._up_pid_values["PrevI"] += I
                up = P + I + D

                # Set previous ts and error for next iteration
                tp = ts
                ep = error

                prev_forward = 0
                prev_right = 0
                prev_up = 0
                if previous_values is not None:
                    prev_forward = previous_values["forward"]
                    prev_right = previous_values["right"]
                    prev_up = previous_values["up"]

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
                    previous_values = {}
                # Set the previous values if we are actuating
                previous_values["forward"] = 0 if is_opposite_dir(forward_setpoint, new_forward) else clamp(new_forward, -100, 100)
                previous_values["right"] = 0 if is_opposite_dir(right_setpoint, new_right) else clamp(new_right, -100, 100)
                previous_values["up"] = 0 if is_opposite_dir(up_setpoint, new_up) else clamp(new_up, -100, 100)

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
        if self._drone(FlyingStateChanged(state="hovering", _policy="check")):
            return True
        return False

    def _is_landed(self):
        if self._drone(FlyingStateChanged(state="landed", _policy="check")):
            return True
        return False

    def _is_home_set(self, location):
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude
        if self._drone(custom_location(latitude=lat,
            longitude=lon, altitude=alt, _policy='check',
            _float_tol=(1e-07, 1e-09))):
            return True
        return False

    def _is_home_reached(self):
        if self._drone(state(state=rth_state.state.available, _policy='check',
            _float_tol=(1e-07, 1e-09))):
            return True
        return False

    def _is_move_by_done(self):
        if self._drone(moveByChanged(status='DONE', _policy='check')):
            return True
        return False

    def _is_move_to_done(self):
        if self._drone(moveToChanged(status='DONE', _policy='check')):
            return True
        return False

    def _is_at_target(self, location):
        lat = location.latitude
        lon = location.longitude
        current_location = self._get_global_position()
        if not current_location:
            return False
        dlat = lat - current_location["latitude"]
        dlon = lon - current_location["longitude"]
        distance =  math.sqrt((dlat ** 2) + (dlon ** 2)) * 1.113195e5
        return distance <= 1.0

    def _is_rel_altitude_reached(self, target_altitude):
        current_altitude = self._get_altitude_rel()
        diff = abs(current_altitude - target_altitude)
        return diff <= 0.5
    
    def _is_abs_altitude_reached(self, target_altitude):
        current_altitude = self._get_global_position()["altitude"]
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
        return abs(north_vel - vels["north"]) <= 0.3 and \
                abs(east_vel - vels["east"]) <= 0.3 and \
                abs(up_vel - vels["up"]) <= 0.3

    def _is_velocity_body_reached(self, velocity):
        forward_vel = velocity.forward_vel
        right_vel = velocity.right_vel
        up_vel = velocity.up_vel
        # Skip angular velocity since we cannot get it
        vels = self._get_velocity_body()
        return abs(forward_vel - vels["forward"]) <= 0.3 and \
                abs(right_vel - vels["right"]) <= 0.3 and \
                abs(up_vel - vels["up"]) <= 0.3

    def _is_heading_reached(self, heading):
        if self._drone(AttitudeChanged(yaw=heading, _policy="check", _float_tol=(1e-3, 1e-1))):
            return True
        return False

    def _is_gimbal_pose_reached(self, yaw, pitch, roll):
        if self._drone(attitude(
                pitch_relative=pitch,
                yaw_relative=yaw, 
                roll_relative=roll, 
                _policy="check", 
                _float_tol=(1e-3, 1e-1)
            )):
            return True
        return False

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
                    logger.info("-- Condition met")
                    return True
            except Exception as e:
                logger.error(f"-- Error evaluating condition: {e}")
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


class PDRAWStreamingThread(threading.Thread):

    def __init__(self, drone):
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

    def run(self):
        self.is_running = True
        self._drone.streaming.start()

        while self.is_running:
            try:
                yuv_frame = self._frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue
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


class FFMPEGStreamingThread(threading.Thread):

    def __init__(self, drone, ip):
        threading.Thread.__init__(self)

        logger.info(f"Using opencv-python version {cv2.__version__}")

        self._current_frame = None
        self.ip = ip
        self._drone = drone
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"
        self.is_running = False

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

