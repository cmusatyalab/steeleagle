import asyncio
import math
import logging

# Streaming Imports
import threading
import time
from concurrent import futures
from enum import Enum
import zmq
import zmq.asyncio

import grpc
import numpy as np

# Interface Imports
from DigitalPerfect.SimulatedDrone import SimulatedDrone

from PIL import Image

# Protocol 
import common_pb2 as common_protocol
from common_pb2 import Request, Response
from messages import telemetry_pb2 as telemetry_protocol
from services import control_service_pb2 as control_protocol
from services import control_service_pb2_grpc
from services.control_service_pb2_grpc import ControlServicer
from google.protobuf.timestamp_pb2 import Timestamp


logger = logging.getLogger("driver/DigitalPerfect")

TELEMETRY_SOCK = 'ipc:///tmp/driver_telem.sock'
# IMAGERY_SOCK = 'ipc:///tmp/imagery.sock'

telemetry_sock = zmq.asyncio.Context().socket(zmq.PUB)
telemetry_sock.bind(TELEMETRY_SOCK)

# cam_sock = zmq.Context().socket(zmq.PUB)
# cam_sock.bind(IMAGERY_SOCK)

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

# Flight modes
class FlightMode(Enum):
    LOITER = "LOITER"
    TAKEOFF_LAND = "TAKEOFF_LAND"
    VELOCITY = "VELOCITY"
    GUIDED = "GUIDED"


class DigitalPerfectDrone(ControlServicer):
    # Constants
    LATDEG_METERS = 1113195
    ALT_TOLERANCE = 0.5
    DEFAULT_IMG_HEIGHT = 720
    DEFAULT_IMG_WIDTH = 1280
    DEFAULT_IMG_CHANNELS = 3
    DEFAULT_TIMEOUT = 30

    def __init__(self, drone_id, **kwargs):
        self._drone_id = drone_id
        self._kwargs = kwargs
        # Drone flight modes and setpoints
        self._velocity_setpoint = None
        self._drone = None
        self._mode = FlightMode.LOITER
        self.ip = "127.0.0.1"
        self._drone = SimulatedDrone(self.ip)

    async def Connect(self, request, context):
        try:
            result = await self._drone.connect()
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

            result = await self._drone.disconnect()
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
            await self._switch_mode(FlightMode.TAKEOFF_LAND)
            logger.info("Takeoff command sent to drone...")
            task_result = asyncio.create_task(self._drone.take_off())
            logger.info(f"Takeoff command result: {task_result}")

            logger.info(f"checking if hovering... {self._is_hovering()}")
            while not self._is_hovering():
                logger.info("Waiting for drone to reach hover state...")
                yield generate_response(resp_type=common_protocol.ResponseStatus.IN_PROGRESS, resp_string="Taking off...")
                await asyncio.sleep(0.1)
                
            logger.info(f"checking if hovering... {self._is_hovering()}")  
            yield generate_response(resp_type=common_protocol.ResponseStatus.IN_PROGRESS, resp_string="Hovering...")
            await self._switch_mode(FlightMode.LOITER)
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
            await self._switch_mode(FlightMode.TAKEOFF_LAND)
            await self._drone.land()

            while not self._is_landed():
                yield generate_response(
                    resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                    resp_string="Landing...",
                )
                await asyncio.sleep(0.1)

            await self._switch_mode(FlightMode.LOITER)
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
            if self._drone.is_stopped():
                yield generate_response(
                    resp_type=common_protocol.ResponseStatus.COMPLETED,
                    resp_string="Drone already in hold state...",
                )
            else:
                self._drone._set_velocity_target(0, 0, 0)
                self._drone.set_angular_velocity(0)
                while not self._is_hovering():
                    yield generate_response(
                        resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                        resp_string="Holding...",
                    )
                    await asyncio.sleep(0.1)
                await self._switch_mode(FlightMode.LOITER)
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
        lat = request.location.latitude
        lon = request.location.longitude
        alt = request.location.altitude
        self._drone.set_home_location(lat, lon, alt)
        return generate_response(
            resp_type=common_protocol.ResponseStatus.COMPLETED,
            resp_string="Home location set successfully",
        )

    async def ReturnToHome(self, request, context):
        try:
            await self._switch_mode(FlightMode.TAKEOFF_LAND)
            await self._drone.return_to_home()

            while not self._is_home_reached():
                yield generate_response(
                    resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                    resp_string="Returning to home...",
                )
                await asyncio.sleep(0.1)

            await self._switch_mode(FlightMode.LOITER)
            yield generate_response(
                resp_type=common_protocol.ResponseStatus.COMPLETED,
                resp_string="Returned to home successfully",
            )
        except Exception as e:
            logger.error(f"Error occurred during return to home: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")

    async def SetGlobalPosition(self, request, context):
        try:
            lat = request.location.latitude
            lon = request.location.longitude
            alt = request.location.altitude
            alt_mode = request.altitude_mode
            hdg_mode = request.heading_mode
            max_velocity = request.max_velocity
            bearing = 0

            if hdg_mode == control_protocol.HeadingMode.TO_TARGET:
                bearing = request.location.heading
           
            # Convert absolute to relative altitude if required
            # TODO: Correct this - DD e_m_t uses an absolute alt unlike anafi drones
            if alt_mode == control_protocol.AltitudeMode.ABSOLUTE:
                altitude = (
                    alt - self._get_global_position()[2] + self._get_altitude_rel()
                )
            else:
                altitude = alt

            await self._switch_mode(FlightMode.GUIDED)

            global_position = self._get_global_position()
            bearing = self._calculate_bearing(
                global_position[0], global_position[1], lat, lon
            )
            if max_velocity:
                if abs(global_position[2] - altitude) < self.ALT_TOLERANCE:
                    max_velocity.z_vel = 0
                await self._drone.extended_move_to(
                    lat,
                    lon,
                    altitude,
                    hdg_mode,
                    bearing,
                    max(max_velocity.x_vel, max_velocity.y_vel),
                    max_velocity.z_vel,
                    max_velocity.angular_vel,
                )
            else:
                await self._drone.move_to(lat, lon, altitude, hdg_mode, bearing)

            while not self._is_move_to_done():
                yield generate_response(
                    resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                    resp_string="Moving to target location...",
                )
                await asyncio.sleep(0.1)

            await self._switch_mode(FlightMode.LOITER)
            if self._is_global_position_reached(lat, lon, altitude):
                yield generate_response(
                    resp_type=common_protocol.ResponseStatus.COMPLETED,
                    resp_string="Reached target location successfully",
                )
            else:
                await context.abort(
                    grpc.StatusCode.INTERNAL, "Failed to reach target location"
                )
        except Exception as e:
            logger.error(f"Error occurred during SetGlobalPosition: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")

    async def SetRelativePosition(self, request, context):
        await context.abort(
            grpc.StatusCode.UNIMPLEMENTED,
            "SetRelativePosition in ENU frame not implemented for digital drone",
        )

    async def Joystick(self, request, context):
        try:
            forward_vel = request.velocity.x_vel
            right_vel = request.velocity.y_vel
            up_vel = request.velocity.z_vel
            angular_vel = request.velocity.angular_vel

            await self._switch_mode(FlightMode.VELOCITY)

            self._velocity_setpoint = (forward_vel, right_vel, up_vel, angular_vel)
            self._drone._set_velocity_target(forward_vel, right_vel, up_vel)
            self._drone.set_angular_velocity(angular_vel)
            return generate_response(
                resp_type=common_protocol.ResponseStatus.COMPLETED,
                resp_string="Joystick set successfully",
            )
        except Exception as e:
            logger.error(f"Error occurred during Joystick: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")

    async def SetVelocity(self, request, context):
        try:
            forward_vel = request.velocity.x_vel
            right_vel = request.velocity.y_vel
            up_vel = request.velocity.z_vel
            angular_vel = request.velocity.angular_vel

            await self._switch_mode(FlightMode.VELOCITY)

            self._velocity_setpoint = (forward_vel, right_vel, up_vel, angular_vel)
            self._drone._set_velocity_target(forward_vel, right_vel, up_vel)
            self._drone.set_angular_velocity(angular_vel)

            await asyncio.sleep(1)

            while not self._drone._check_target_active("velocity"):
                yield generate_response(
                    resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                    resp_string="Setting velocity...",
                )
                await asyncio.sleep(0.1)
            yield generate_response(
                resp_type=common_protocol.ResponseStatus.COMPLETED,
                resp_string="Velocity set successfully",
            )
        except Exception as e:
            logger.error(f"Error occurred during SetVelocity: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")

    async def SetHeading(self, request, context):
        try:
            lat = request.location.latitude
            lon = request.location.longitude
            bearing = request.location.heading
            heading_mode = request.heading_mode

            global_position = self._get_global_position()
            target = None
            if heading_mode == control_protocol.HeadingMode.HEADING_START:
                target = bearing
            else:
                target = self._calculate_bearing(
                    global_position[0], global_position[1], lat, lon
                )

            await self._drone.move_to(
                global_position[0],
                global_position[1],
                global_position[2],
                control_protocol.HeadingMode.TO_TARGET,
                target,
            )  # Yaw in place

            while not self._is_heading_reached(target):
                yield generate_response(
                    resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                    resp_string="Setting heading...",
                )
                await asyncio.sleep(0.1)
            yield generate_response(
                resp_type=common_protocol.ResponseStatus.COMPLETED,
                resp_string="Heading set successfully",
            )
        except Exception as e:
            logger.error(f"Error occurred during SetHeading: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")

    async def SetGimbalPose(self, request, context):
        try:
            yaw = request.pose.yaw
            pitch = request.pose.pitch
            roll = request.pose.roll
            control_mode = request.mode

            if control_mode == common_protocol.PoseMode.ANGLE:
                target_yaw = min(360, max(0, yaw))
                target_pitch = min(360, max(0, pitch))
                target_roll = min(360, max(0, roll))

                await self._drone.set_target(
                    gimbal_id=0,
                    control_mode="position",
                    pitch=target_pitch,
                    roll=target_roll,
                    yaw=target_yaw,
                )
            elif control_mode == common_protocol.PoseMode.OFFSET:
                current_gimbal = self._get_gimbal_pose_body(request.pose.actuator_id)
                target_pitch = min(360, max(0, current_gimbal["g_pitch"] + pitch))
                target_roll = min(360, max(0, current_gimbal["g_roll"] + roll))
                target_yaw = min(360, max(0, current_gimbal["g_yaw"] + yaw))

                await self._drone.set_target(
                    gimbal_id=0,
                    control_mode="position",
                    pitch=target_pitch,
                    roll=target_roll,
                    yaw=target_yaw,
                )
            else:
                target_pitch = None
                target_roll = None
                target_yaw = None
                logger.error("Error with setting target gimbal pose characteristics...")
                await self._drone.set_target(
                    gimbal_id=0,
                    control_mode="velocity",
                    pitch=target_pitch,
                    roll=target_roll,
                    yaw=target_yaw,
                )
            while not self._is_gimbal_pose_reached(
                target_pitch, target_roll, target_yaw
            ):
                yield generate_response(
                    resp_type=common_protocol.ResponseStatus.IN_PROGRESS,
                    resp_string="Setting gimbal pose...",
                )
                await asyncio.sleep(0.1)
            yield generate_response(
                resp_type=common_protocol.ResponseStatus.COMPLETED,
                resp_string="Gimbal pose set successfully",
            )

        except Exception as e:
            logger.error(f"Error occurred during SetGimbalPose: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, f"Unexpected error: {str(e)}")

    async def ConfigureTelemetryStream(self, request, context):
        self.telemetry_task = asyncio.create_task(self.stream_telemetry(telemetry_sock, request.frequency))
        return generate_response(2)

    async def stream_telemetry(self, tel_sock, rate_hz):
        logger.info("Starting telemetry stream")
        await asyncio.sleep(1)

        while self._is_connected():
            try:
                tel_message = telemetry_protocol.DriverTelemetry()

                tel_message.vehicle_info.name = self._get_name()
                tel_message.vehicle_info.model = self._get_type()
                tel_message.vehicle_info.battery_info.percentage = (
                    self._get_battery_percentage()
                )
                tel_message.vehicle_info.gps_info.satellites = self._get_satellites()
                tel_message.position_info.global_position.latitude = (
                    self._get_global_position()[0]
                )
                tel_message.position_info.global_position.longitude = (
                    self._get_global_position()[1]
                )
                tel_message.position_info.global_position.altitude = (
                    self._get_global_position()[2]
                )

                tel_message.position_info.global_position.heading = self._get_heading()
                tel_message.position_info.relative_position.z = self._get_altitude_rel()
                tel_message.position_info.velocity_neu.x_vel = self._get_velocity_neu()[
                    "north"
                ]
                tel_message.position_info.velocity_neu.y_vel = self._get_velocity_neu()[
                    "east"
                ]
                tel_message.position_info.velocity_neu.z_vel = self._get_velocity_neu()[
                    "up"
                ]
                tel_message.position_info.velocity_body.x_vel = (
                    self._get_velocity_body()["forward"]
                )
                tel_message.position_info.velocity_body.y_vel = (
                    self._get_velocity_body()["right"]
                )
                tel_message.position_info.velocity_body.z_vel = (
                    self._get_velocity_body()["up"]
                )
                tel_message.position_info.velocity_body.angular_vel = (
                    self._drone.get_angular_velocity()
                )
                gimbal = self._get_gimbal_pose_body(0)
                tel_message.gimbal_info.gimbals.append(telemetry_protocol.GimbalStatus(id=0))
                tel_message.gimbal_info.gimbals[0].pose_body.pitch = gimbal["g_pitch"]
                tel_message.gimbal_info.gimbals[0].pose_body.roll = gimbal["g_roll"]
                tel_message.gimbal_info.gimbals[0].pose_body.yaw = gimbal["g_yaw"]
                tel_message.gimbal_info.gimbals[0].id = 0
                #tel_message.status = self._get_current_status()
                batt = self._get_battery_percentage()

                # Warnings
                if batt <= 15:
                    tel_message.alert_info.battery_warning = (
                        telemetry_protocol.BatteryWarning.CRITICAL
                    )
                elif batt <= 30:
                    tel_message.alert_info.battery_warning = (
                        telemetry_protocol.BatteryWarning.LOW
                    )
                mag = self._get_magnetometer()
                if mag == 2:
                    tel_message.alert_info.magnetometer_warning = (
                        telemetry_protocol.MagnetometerWarning.NO_MAGNETOMETER_WARNING
                    )
                elif mag == 1:
                    tel_message.alert_info.magnetometer_warning = (
                        telemetry_protocol.MagnetometerWarning.PERTURBATION
                    )
                sats = self._get_satellites()
                if sats == 0:
                    tel_message.alert_info.gps_warning = (
                        telemetry_protocol.GPSWarning.NO_GPS_WARNING
                    )
                elif sats <= 10:
                    tel_message.alert_info.gps_warning = (
                        telemetry_protocol.GPSWarning.WEAK_WEAK
                    )
                await tel_sock.send_multipart([b'driver_telemetry', tel_message.SerializeToString()])
            except Exception as e:
                logger.error(f"Failed to get telemetry, error: {e}")
            await asyncio.sleep(1.0 / rate_hz)

    #    async def stream_video(self, cam_sock, rate_hz):
    #        logger.info("Starting camera stream")
    #        self._start_streaming()
    #        frame_id = 0
    #        while self._is_connected():
    #            try:
    #                cam_message = data_protocol.Frame()
    #                frame, frame_shape = await self._get_video_frame()
    #
    #                if frame is None:
    #                    logger.error("Failed to get video frame")
    #                    continue
    #
    #                cam_message.data = frame
    #                cam_message.height = frame_shape[1]
    #                cam_message.width = frame_shape[0]
    #                cam_message.channels = frame_shape[2]
    #                cam_message.id = frame_id
    #                cam_sock.send(cam_message.SerializeToString())
    #                frame_id = frame_id + 1
    #            except Exception as e:
    #                logger.error(f"Failed to get video frame, error: {e}")
    #            await asyncio.sleep(1.0 / rate_hz)
    #        self._stop_streaming()
    #        logger.info("Camera stream ended, disconnected from drone")

    """ Telemetry methods """

    def _get_altitude_rel(self) -> float:
        alt = self._drone.get_current_position()[2]
        if alt is not None:
            return alt
        else:
            logger.error("Failed to extract relative alt from drone")
            return 0.0

    def _get_attitude(self) -> dict[str, float]:
        att = self._drone.get_state("attitude")
        rad_to_deg = 180 / math.pi
        return {
            "pitch": att["pitch"] * rad_to_deg,
            "roll": att["roll"] * rad_to_deg,
            "yaw": att["yaw"] * rad_to_deg,
        }

    def _get_battery_percentage(self) -> int:
        return int(self._drone.get_state("battery_percent"))

    def _get_current_status(self) -> telemetry_protocol.MotionStatus:
        return self._drone.get_state("flight_state")

    def _get_gimbal_pose_body(self, gimbal_id) -> dict[str, float]:
        # Currently ignores gimbal_id
        return self._drone.get_state("gimbal_pose")

    def _get_global_position(self) -> tuple[float | None, float | None, float | None]:
        return self._drone.get_current_position()

    def _get_heading(self) -> float:
        return math.degrees(self._drone.get_state("attitude")["yaw"]) % 360

    def _get_magnetometer(self) -> int:
        return self._drone.get_state("magnetometer")

    def _get_type(self) -> str:
        try:
            return self._drone._device_type
        except:
            return "Digital Simulated"

    def _get_name(self) -> str:
        return self._drone_id

    def _get_satellites(self) -> int:
        return self._drone.get_state("satellite_count")

    def _get_velocity_neu(self) -> dict[str, float]:
        ned = self._drone.get_state("velocity")
        return {"north": ned["speedX"], "east": ned["speedY"], "up": ned["speedZ"]}

    def _get_velocity_body(self) -> dict[str, float]:
        neu = self._get_velocity_neu()
        vec = np.array([neu["north"], neu["east"]], dtype=float)
        vecf = np.array([0.0, 1.0], dtype=float)

        hd = (self._get_heading()) + 90
        fw = np.radians(hd)
        c, s = np.cos(fw), np.sin(fw)
        R1 = np.array(((c, -s), (s, c)))
        vecf = np.dot(R1, vecf)

        vecr = np.array([0.0, 1.0], dtype=float)
        rt = np.radians(hd + 90)
        c, s = np.cos(rt), np.sin(rt)
        R2 = np.array(((c, -s), (s, c)))
        vecr = np.dot(R2, vecr)

        res = {
            "forward": np.dot(vec, vecf) * -1,
            "right": np.dot(vec, vecr) * -1,
            "up": neu["up"],
        }
        return res

    """ Actuation methods """

    async def _switch_mode(self, mode):
        self._mode = mode

    """ ACK methods """

    def _is_abs_altitude_reached(self, target_altitude: float) -> bool:
        # Assumes absolute and relative altitude are stored the same currently
        current_altitude = self._get_global_position()[2]
        if current_altitude is None:
            return False
        distance = abs(current_altitude - target_altitude)
        return distance < 1.0

    def _is_at_target(self, lat: float, lon: float) -> bool:
        current_location = self._get_global_position()
        if (
            not current_location
            or current_location[0] is None
            or current_location[1] is None
        ):
            return False
        dlat = lat - current_location[0]
        dlon = lon - current_location[1]
        distance = math.sqrt((dlat**2) + (dlon**2)) * self.LATDEG_METERS
        return distance < 1.0

    def _is_connected(self):
        return self._drone.connection_state()

    def _is_gimbal_pose_reached(self, pitch: float, roll: float, yaw: float) -> bool:
        current_pose = self._drone.get_state("gimbal_pose")
        pose_array = [
            current_pose["g_pitch"],
            current_pose["g_roll"],
            current_pose["g_yaw"],
        ]
        return np.allclose(pose_array, [pitch, roll, yaw], rtol=1e-1, atol=1e-3)

    def _is_global_position_reached(self, lat: float, lon: float, alt: float) -> bool:
        return self._is_abs_altitude_reached(alt) and self._is_at_target(lat, lon)

    def _is_heading_reached(self, target) -> bool:
        current_heading = self._drone.get_state("attitude")["yaw"]
        return np.allclose(current_heading, target, atol=1e-3, rtol=1e-1)

    def _is_home_reached(self) -> bool:
        return np.allclose(
            self._drone.get_home_location(),
            self._drone.get_current_position(),
            rtol=1e-05,
            atol=1e-07,
        )

    def _is_home_set(self, lat, lon, alt) -> bool:
        return np.allclose(
            [lat, lon, alt], self._drone.get_home_location(), rtol=1e-07, atol=1e-09
        )

    def _is_hovering(self) -> bool:
        return self._drone.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    def _is_landed(self) -> bool:
        return self._drone.check_flight_state(
            telemetry_protocol.MotionStatus.MOTORS_OFF
        )

    def _is_move_to_done(self) -> bool:
        return self._drone._position_flag

    def _is_move_by_done(self) -> bool:
        return self._drone._position_flag

    """ Helper methods """

    def _calculate_bearing(self, lat1, lon1, lat2, lon2):
        # Convert latitude and longitude from degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        delta_lon = lon2 - lon1

        # Bearing calculation
        x = math.sin(delta_lon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(
            lat2
        ) * math.cos(delta_lon)

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

    def _start_streaming(self):
        logger.info("Using simulated streaming thread for streaming")
        self._streaming_thread = SimulatedStreamingThread(self._drone, self.ip)
        self._streaming_thread.start()

    async def _get_video_frame(self):
        if self._streaming_thread:
            return self._streaming_thread.grab_frame().tobytes(), (
                self.DEFAULT_IMG_WIDTH,
                self.DEFAULT_IMG_HEIGHT,
                self.DEFAULT_IMG_CHANNELS,
            )

    async def _stop_streaming(self):
        self._streaming_thread.stop()


class SimulatedStreamingThread(threading.Thread):
    def __init__(self, drone, ip, image_set_path=None):
        threading.Thread.__init__(self)

        self._current_frame = None
        self.ip = ip
        self._drone = drone
        self.is_running = False
        self.image_path = image_set_path
        self.frame_index = 0

    def run(self):
        while not self.is_running:
            self.is_running = True
            while self.is_running:
                try:
                    if self.image_path:
                        self._current_frame = Image.open(
                            f"{self.image_path}_{self.frame_index}"
                        )
                        self.frame_index += 1
                    else:
                        continue
                except Exception as e:
                    logger.error(f"Frame could not be read. {e}")

    def grab_frame(self):
        try:
            if self._current_frame is None:
                return np.full(
                    (
                        self.DEFAULT_IMG_WIDTH,
                        self.DEFAULT_IMG_HEIGHT,
                        self.DEFAULT_IMG_CHANNELS,
                    ),
                    255,
                    dtype=np.uint8,
                )
            frame = self._current_frame.copy()
            return frame
        except Exception as e:
            logger.error(f"Grab frame failed: {e}")
            # Send blank image
            return np.full(
                (
                    self.DEFAULT_IMG_WIDTH,
                    self.DEFAULT_IMG_HEIGHT,
                    self.DEFAULT_IMG_CHANNELS,
                ),
                255,
                dtype=np.uint8,
            )

    def stop(self):
        self.is_running = False
