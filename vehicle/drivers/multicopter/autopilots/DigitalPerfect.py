# General Imports
import asyncio
import logging
import math

# Streaming Imports
import threading
import time
from enum import Enum

# Protocol Imports
import common_pb2 as common_protocol
import dataplane_pb2 as data_protocol
import numpy as np

# Interface Imports
from autopilots.SimulatedDrone import SimulatedDrone
from multicopter.multicopter_interface import MulticopterItf
from PIL import Image

logger = logging.getLogger(__name__)

LATDEG_METERS = 1113195
DEFAULT_IMG_HEIGHT = 720
DEFAULT_IMG_WIDTH = 1280
DEFAULT_IMG_CHANNELS = 3
DEFAULT_TIMEOUT = 30


class FlightMode(Enum):
    LOITER = "LOITER"
    TAKEOFF_LAND = "TAKEOFF_LAND"
    VELOCITY = "VELOCITY"
    GUIDED = "GUIDED"


class DigitalPerfect(MulticopterItf):
    def __init__(self, drone_id, **kwargs):
        self._drone_id = drone_id
        self._kwargs = kwargs
        # Drone flight modes and setpoints
        self._velocity_setpoint = None
        self._drone = None
        self._mode = FlightMode.LOITER
        self.ip = "127.0.0.1"
        self._drone = SimulatedDrone(self.ip)

        """ Interface methods """

    async def get_type(self) -> str:
        try:
            return self._drone._device_type
        except:
            return "Digital Simulated"

    async def connect(self, connection_string) -> bool:
        # Create the digital drone object
        result = await self._drone.connect()
        if not result:
            self._drone = None
        return result

    async def disconnect(self) -> None:
        result = await self._drone.disconnect()
        if result:
            self._drone = None
            logger.info("Completed disconnection from digital drone...")
        else:
            logger.error("Failed to properly disconnect from digital drone...")
        return

    async def take_off(self) -> common_protocol.ResponseStatus:
        await self._switch_mode(FlightMode.TAKEOFF_LAND)
        task_result = await self._drone.take_off()

        result = await self._wait_for_condition(
            lambda: self._is_hovering(), timeout=DEFAULT_TIMEOUT, interval=1
        )

        await self._switch_mode(FlightMode.LOITER)
        if task_result and result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def land(self) -> common_protocol.ResponseStatus:
        await self._switch_mode(FlightMode.TAKEOFF_LAND)
        task_result = await self._drone.land()

        result = await self._wait_for_condition(
            lambda: self._is_landed(), timeout=DEFAULT_TIMEOUT, interval=1
        )

        await self._switch_mode(FlightMode.LOITER)

        if task_result and result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def hover(self) -> common_protocol.ResponseStatus:
        velocity = common_protocol.VelocityBody()
        velocity.forward_vel = 0.0
        velocity.right_vel = 0.0
        velocity.up_vel = 0.0
        velocity.angular_vel = 0.0
        await self.set_velocity_body(velocity)

        result = await self._wait_for_condition(
            lambda: self._is_hovering(), timeout=DEFAULT_TIMEOUT, interval=1
        )

        await self._switch_mode(FlightMode.LOITER)

        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def kill(self):
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def set_home(self, location: common_protocol.Location):
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude

        try:
            self._drone.set_home_location(lat, lon, alt)
        except:
            return common_protocol.ResponseStatus.FAILED

        result = await self._wait_for_condition(
            lambda: self._is_home_set(lat, lon, alt), timeout=5, interval=0.1
        )

        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def rth(self):
        await self._switch_mode(FlightMode.TAKEOFF_LAND)

        try:
            await self._drone.return_to_home()
        except:
            return common_protocol.ResponseStatus.FAILED

        await asyncio.sleep(1)

        result = await self._wait_for_condition(
            lambda: self._is_home_reached(), interval=1
        )

        await self._switch_mode(FlightMode.LOITER)
        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def set_global_position(self, location: common_protocol.Location):
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude
        alt_mode = location.altitude_mode
        hdg_mode = location.heading_mode
        max_velocity = None

        if hdg_mode == common_protocol.LocationHeadingMode.TO_TARGET:
            bearing = location.heading
        else:
            bearing = 0
        if location.max_velocity is not None:
            max_velocity = location.max_velocity

        # Convert absolute to relative altitude if required
        if alt_mode == common_protocol.LocationAltitudeMode.ABSOLUTE:
            altitude = alt - self._get_global_position()[2] + self._get_altitude_rel()
        else:
            altitude = alt

        await self._switch_mode(FlightMode.GUIDED)

        try:
            global_position = self._get_global_position()
            bearing = self._calculate_bearing(
                global_position[0], global_position[1], lat, lon
            )
            if max_velocity:
                await self._drone.extended_move_to(
                    lat,
                    lon,
                    altitude,
                    hdg_mode,
                    bearing,
                    max(max_velocity.north_vel, max_velocity.east_vel),
                    max_velocity.up_vel,
                    max_velocity.angular_vel,
                )
            else:
                await self._drone.move_to(lat, lon, altitude, hdg_mode, bearing)
        except:
            await self._switch_mode(FlightMode.LOITER)
            return common_protocol.ResponseStatus.FAILED

        await asyncio.sleep(1)

        result = await self._wait_for_condition(
            lambda: self._is_move_to_done(), interval=1
        )

        await self._switch_mode(FlightMode.LOITER)

        if self._is_global_position_reached(lat, lon, altitude) and result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def set_relative_position_enu(self, position):
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def set_relative_position_body(self, position):
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def set_velocity_enu(self, velocity):
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def set_velocity_body(self, velocity: common_protocol.VelocityBody):
        forward_vel = velocity.forward_vel
        right_vel = velocity.right_vel
        up_vel = velocity.up_vel
        angular_vel = velocity.angular_vel

        await self._switch_mode(FlightMode.VELOCITY)

        self._velocity_setpoint = (forward_vel, right_vel, up_vel, angular_vel)
        self._drone._set_velocity_target(forward_vel, right_vel, up_vel)
        self._drone.set_angular_velocity(angular_vel)

        await asyncio.sleep(1)

        if self._drone._check_target_active("velocity"):
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def set_heading(self, location: common_protocol.Location):
        lat = location.latitude
        lon = location.longitude
        bearing = location.bearing
        heading_mode = location.heading_mode

        global_position = self._get_global_position()

        if heading_mode == common_protocol.LocationHeadingMode.HEADING_START:
            target = bearing
        else:
            target = self._calculate_bearing(
                global_position[0], global_position[1], lat, lon
            )

        await self._drone.move_to(
            global_position[0],
            global_position[1],
            global_position[2],
            common_protocol.LocationHeadingMode.TO_TARGET,
            target,
        )  # Yaw in place

        result = await self._wait_for_condition(
            lambda: self._is_heading_reached(target),
            timeout=DEFAULT_TIMEOUT,
            interval=0.5,
        )

        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.RepsonseStatus.FAILED

    async def set_gimbal_pose(self, pose: common_protocol.PoseBody):
        yaw = pose.yaw
        pitch = pose.pitch
        roll = pose.roll
        control_mode = pose.control_mode

        try:
            if control_mode == common_protocol.PoseControlMode.POSITION_ABSOLUTE:
                target_yaw = yaw
                target_pitch = pitch
                target_roll = roll

                await self._drone.set_target(
                    gimbal_id=0,
                    control_mode="position",
                    pitch=target_pitch,
                    roll=target_roll,
                    yaw=target_yaw,
                )
            elif control_mode == common_protocol.PoseControlMode.POSITION_RELATIVE:
                current_gimbal = self._get_gimbal_pose_body(pose.actuator_id)
                target_pitch = current_gimbal["g_pitch"] + pitch
                target_roll = current_gimbal["g_roll"] + roll
                target_yaw = current_gimbal["g_yaw"] + yaw

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

                await self._drone.set_target(
                    gimbal_id=0,
                    control_mode="velocity",
                    pitch=target_pitch,
                    roll=target_roll,
                    yaw=target_yaw,
                )
        except:
            return common_protocol.ResponseStatus.FAILED

        if control_mode != common_protocol.PoseControlMode.VELOCITY:
            result = await self._wait_for_condition(
                lambda: self._is_gimbal_pose_reached(
                    target_pitch, target_roll, target_yaw
                ),
                timeout=DEFAULT_TIMEOUT,
                interval=0.5,
            )
        else:
            result = True

        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def stream_telemetry(self, tel_sock, rate_hz):
        logger.info("Starting telemetry stream")
        await asyncio.sleep(1)

        while await self.is_connected():
            try:
                tel_message = data_protocol.Telemetry()
                tel_message.drone_name = self._get_name()
                tel_message.drone_model = await self.get_type()
                tel_message.battery = self._get_battery_percentage()
                tel_message.satellites = self._get_satellites()
                tel_message.global_position.latitude = self._get_global_position()[0]
                tel_message.global_position.longitude = self._get_global_position()[1]
                tel_message.global_position.altitude = self._get_global_position()[2]
                tel_message.relative_position.up = self._get_altitude_rel()
                tel_message.global_position.heading = self._get_heading()
                tel_message.velocity_enu.north_vel = self._get_velocity_enu()["north"]
                tel_message.velocity_enu.east_vel = self._get_velocity_enu()["east"]
                tel_message.velocity_enu.up_vel = self._get_velocity_enu()["up"]
                tel_message.velocity_body.forward_vel = self._get_velocity_body()[
                    "forward"
                ]
                tel_message.velocity_body.right_vel = self._get_velocity_body()["right"]
                tel_message.velocity_body.up_vel = self._get_velocity_body()["up"]
                gimbal = self._get_gimbal_pose_body(0)
                tel_message.gimbal_pose.pitch = gimbal["g_pitch"]
                tel_message.gimbal_pose.roll = gimbal["g_roll"]
                tel_message.gimbal_pose.yaw = gimbal["g_yaw"]
                tel_message.gimbal_pose.control_mode = (
                    common_protocol.PoseControlMode.POSITION_ABSOLUTE
                )
                tel_message.gimbal_pose.actuator_id = 0
                tel_message.status = self._get_current_status()
                batt = tel_message.battery

                # Warnings
                if batt <= 15:
                    tel_message.alerts.battery_warning = (
                        common_protocol.BatteryWarning.CRITICAL
                    )
                elif batt <= 30:
                    tel_message.alerts.battery_warning = (
                        common_protocol.BatteryWarning.LOW
                    )
                mag = self._get_magnetometer()
                if mag == 2:
                    tel_message.alerts.magnetometer_warning = (
                        common_protocol.MagnetometerWarning.RECOMMENDED
                    )
                elif mag == 1:
                    tel_message.alerts.magnetometer_warning = (
                        common_protocol.MagnetometerWarning.REQUIRED
                    )
                sats = tel_message.satellites
                if sats == 0:
                    tel_message.alerts.gps_warning = (
                        common_protocol.GPSWarning.NO_SIGNAL
                    )
                elif sats <= 10:
                    tel_message.alerts.gps_warning = common_protocol.GPSWarning.WEAK

                tel_sock.send(tel_message.SerializeToString())
            except Exception as e:
                logger.error(f"Failed to get telemetry, error: {e}")
            await asyncio.sleep(1.0 / rate_hz)

    async def stream_video(self, cam_sock, rate_hz):
        logger.info("Starting camera stream")
        self._start_streaming()
        frame_id = 0
        while await self.is_connected():
            try:
                cam_message = data_protocol.Frame()
                frame, frame_shape = await self._get_video_frame()

                if frame is None:
                    logger.error("Failed to get video frame")
                    continue

                cam_message.data = frame
                cam_message.height = frame_shape[0]
                cam_message.width = frame_shape[1]
                cam_message.channels = frame_shape[2]
                cam_message.id = frame_id
                cam_sock.send(cam_message.SerializeToString())
                frame_id = frame_id + 1
            except Exception as e:
                logger.error(f"Failed to get video frame, error: {e}")
            await asyncio.sleep(1.0 / rate_hz)
        self._stop_streaming()
        logger.info("Camera stream ended, disconnected from drone")

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

    def _get_current_status(self) -> common_protocol.FlightStatus:
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

    def _get_name(self) -> str:
        return self._drone_id

    def _get_satellites(self) -> int:
        return self._drone.get_state("satellite_count")

    def _get_velocity_enu(self) -> dict[str, float]:
        ned = self._drone.get_state("velocity")
        return {"north": ned["speedX"], "east": ned["speedY"], "up": ned["speedZ"]}

    def _get_velocity_body(self) -> dict[str, float]:
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
        R2 = np.array(((c, -s), (s, c)))
        vecr = np.dot(R2, vecr)

        res = {
            "forward": np.dot(vec, vecf) * -1,
            "right": np.dot(vec, vecr) * -1,
            "up": enu["up"],
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
        distance = math.sqrt((dlat**2) + (dlon**2)) * LATDEG_METERS
        return distance < 1.0

    async def is_connected(self):
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
        return self._drone.check_flight_state(common_protocol.FlightStatus.HOVERING)

    def _is_landed(self) -> bool:
        return self._drone.check_flight_state(common_protocol.FlightStatus.LANDED)

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
                DEFAULT_IMG_WIDTH,
                DEFAULT_IMG_HEIGHT,
                DEFAULT_IMG_CHANNELS,
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
                return np.zeros(
                    (DEFAULT_IMG_WIDTH, DEFAULT_IMG_HEIGHT, DEFAULT_IMG_CHANNELS)
                )
            frame = self._current_frame.copy()
            return frame
        except Exception as e:
            logger.error(f"Grab frame failed: {e}")
            # Send blank image
            return np.zeros(
                (DEFAULT_IMG_WIDTH, DEFAULT_IMG_HEIGHT, DEFAULT_IMG_CHANNELS)
            )

    def stop(self):
        self.is_running = False
