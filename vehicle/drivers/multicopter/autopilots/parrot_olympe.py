# General imports
import math
import time
import asyncio
import logging
from enum import Enum
import numpy as np
import cv2
# SDK imports (Olympe)
import olympe
from olympe import Drone
from olympe.messages.ardrone3.Piloting import TakeOff, Landing
from olympe.messages.ardrone3.Piloting import PCMD, moveTo, moveBy
from olympe.messages.rth import set_custom_location, return_to_home, custom_location, state
import olympe.enums.rth as rth_state
from olympe.messages.common.CommonState import BatteryStateChanged
from olympe.messages.ardrone3.SpeedSettingsState import MaxVerticalSpeedChanged, MaxRotationSpeedChanged
from olympe.messages.ardrone3.PilotingState import AttitudeChanged, GpsLocationChanged, AltitudeChanged, FlyingStateChanged, SpeedChanged
from olympe.messages.ardrone3.GPSState import NumberOfSatelliteChanged
from olympe.messages.gimbal import set_target, attitude
import olympe.enums.gimbal as gimbal_mode
import olympe.enums.move as move_mode
from olympe.messages.common.CalibrationState import MagnetoCalibrationRequiredState
# Interface import
from multicopter.multicopter_interface import MulticopterItf
# Protocol imports
import dataplane_pb2 as data_protocol
import common_pb2 as common_protocol
# Streaming imports
import threading
import queue

logger = logging.getLogger(__name__)

class ParrotOlympeDrone(MulticopterItf):

    class FlightMode(Enum):
        LOITER = 'LOITER'
        TAKEOFF_LAND = 'TAKEOFF_LAND'
        VELOCITY = 'VELOCITY'
        GUIDED = 'GUIDED'

    def __init__(self, drone_id, **kwargs):
        self._drone_id = drone_id
        # Drone flight modes and setpoints
        self._velocity_setpoint = None
        # Set PID values for the drone
        self._forward_pid_values = {}
        self._right_pid_values = {}
        self._up_pid_values = {}
        self._pid_task = None
        self._mode = ParrotOlympeDrone.FlightMode.LOITER

    ''' Interface methods '''
    async def get_type(self):
        return "Parrot Olympe Drone"

    async def connect(self, connection_string):
        self.ip = connection_string
        # Create the drone object
        self._drone = Drone(self.ip)
        # Connect to drone
        return self._drone.connect()

    async def is_connected(self):
        return self._drone.connection_state()

    async def disconnect(self):
        self._drone.disconnect()

    async def take_off(self):
        await self._switch_mode(ParrotOlympeDrone.FlightMode.TAKEOFF_LAND)
        self._drone(TakeOff())
        result = await self._wait_for_condition(
            lambda: self._is_hovering(),
            interval=1
        )

        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def land(self):
        await self._switch_mode(ParrotOlympeDrone.FlightMode.TAKEOFF_LAND)
        self._drone(Landing()).wait().success()
        result = await self._wait_for_condition(
            lambda: self._is_landed(),
            interval=1
        )

        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def hover(self):
        velocity = common_protocol.VelocityBody()
        velocity.forward_vel = 0.0
        velocity.right_vel = 0.0
        velocity.up_vel = 0.0
        velocity.angular_vel = 0.0
        return await self.set_velocity_body(velocity)

    async def kill(self):
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def set_home(self, location):
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude
        
        try:
            self._drone(set_custom_location(
                lat, lon, alt)).wait().success()
        except:
            return common_protocol.ResponseStatus.FAILED

        result = await self._wait_for_condition(
            lambda: self._is_home_set(lat, lon, alt),
            timeout=5,
            interval=0.1
        )

        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def rth(self):
        await self._switch_mode(ParrotOlympeDrone.FlightMode.TAKEOFF_LAND)
        
        try:
            self._drone(return_to_home()).success()
        except:
            return common_protocol.ResponseStatus.FAILED
        
        await asyncio.sleep(1)

        result = await self._wait_for_condition(
            lambda: self._is_home_reached(),
            interval=1
        )

        return common_protocol.ResponseStatus.COMPLETED

    async def set_global_position(self, location):
        lat = location.latitude
        lon = location.longitude
        alt = location.absolute_altitude
        rel_alt = location.relative_altitude
        bearing = location.heading

        # TODO: Make it so we can select relative or absolute altitude
        # altitude = rel_alt if location.has_relative_alt() else alt - self._get_global_position()["altitude"]
        altitude = alt - self._get_global_position()["altitude"] + self._get_altitude_rel()

        await self._switch_mode(ParrotOlympeDrone.FlightMode.GUIDED)
        try:
            if bearing is None:
                self._drone(
                    moveTo(lat, lon, altitude, move_mode.orientation_mode.to_target, 0.0)
                ).success()
            else:
                self._drone(
                    moveTo(lat, lon, altitude, move_mode.orientation_mode.heading_start, bearing)
                ).success()
        except:
            return common_protocol.ResponseStatus.FAILED

        result = await self._wait_for_condition(
            lambda: self._is_global_position_reached(lat, lon, altitude),
            interval=1
        )

        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def set_relative_position_enu(self, position):
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def set_relative_position_body(self, position):
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def set_velocity_enu(self, velocity):
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def set_velocity_body(self, velocity):
        forward_vel = velocity.forward_vel
        right_vel = velocity.right_vel
        up_vel = velocity.up_vel
        angular_vel = velocity.angular_vel

        await self._switch_mode(ParrotOlympeDrone.FlightMode.VELOCITY)

        # Check that the speeds is within the drone bounds
        max_rotation = self._drone.get_state(MaxRotationSpeedChanged)["max"]
        max_vertical_speed = self._drone.get_state(MaxVerticalSpeedChanged)["max"]

        if abs(angular_vel) > max_rotation:
            return common_protocol.ResponseStatus.FAILED
        if abs(up_vel) > max_vertical_speed:
            return common_protocol.ResponseStatus.FAILED

        self._velocity_setpoint = \
                (forward_vel, right_vel, up_vel, angular_vel)
        if self._pid_task is None:
            self._pid_task = asyncio.create_task(\
                    self._velocity_pid())

        return common_protocol.ResponseStatus.COMPLETED

    async def set_heading(self, location):
        lat = location.latitude
        lon = location.longitude
        bearing = location.bearing
        heading = self._get_heading()

        if lat is None and lon is None:
            target = bearing
        else:
            gp = self._get_global_position()
            target = self._calculate_bearing(\
                    gp["latitude"], gp["longitude"],\
                    lat, lon)
        offset = (heading - target) * (math.pi / 180.0)

        try:
            self._drone(moveBy(0.0, 0.0, 0.0, offset)).success()
        except:
            return common_protocol.ResponseStatus.FAILED

        result = await self._wait_for_condition(
            lambda: self._heading_reached(target),
            interval=0.5
        )

        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def set_gimbal_pose(self, pose):
        yaw = pose.yaw
        pitch = pose.pitch
        roll = pose.roll
        
        # Actuate the gimbal
        try:
            self._drone(set_target(
                gimbal_id=0,
                control_mode="position",
                yaw_frame_of_reference="none",
                yaw=yaw,
                pitch_frame_of_reference="absolute",
                pitch=pitch,
                roll_frame_of_reference="none",
                roll=roll)
            ).success()
        except:
            return common_protocol.ResponseStatus.FAILED

        result = await self._wait_for_condition(
            lambda: self._is_gimbal_pose_reached(yaw, pitch, roll),
            interval=0.5
        )
        
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
                tel_message.global_position.absolute_altitude = \
                    self._get_global_position()["altitude"]
                tel_message.global_position.relative_altitude = \
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
                batt = tel_message.battery
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
            await asyncio.sleep(1 / rate_hz)

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
            await asyncio.sleep(1 / rate_hz)
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
        return {"roll": att["roll"] * rad_to_deg, \
                "pitch": att["pitch"] * rad_to_deg, \
                "yaw": att["yaw"] * rad_to_deg}

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
        return math.degrees(self._drone.get_state(AttitudeChanged)["yaw"])

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

        res = {"forward": np.dot(vec, vecf) * -1, \
                "right": np.dot(vec, vecr) * -1, \
                "up": enu["up"]}
        return res

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

            while self._mode == ParrotOlympeDrone.FlightMode.VELOCITY:
                current = self._get_velocity_body()
                forward_setpoint, right_setpoint, up_setpoint, angular_setpoint = self._velocity_setpoint

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
                previous_values["forward"] = 0 if is_opposite_dir(forward_setpoint, new_forward) else new_forward
                previous_values["right"] = 0 if is_opposite_dir(right_setpoint, new_right) else new_right
                previous_values["up"] = 0 if is_opposite_dir(up_setpoint, new_up) else new_up

                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            self._forward_pid_values["PrevI"] = 0.0
            self._right_pid_values["PrevI"] = 0.0
            self._up_pid_values["PrevI"] = 0.0
        except Exception as e:
            logger.error(f"PID iteration failure, reason: {e}")

    ''' Actuation methods '''
    async def _switch_mode(self, mode):
        if self._mode == mode:
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

    def _is_home_set(self, lat, lon, alt):
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

    def _is_at_target(self, lat, lon):
        current_location = self._get_global_position()
        if not current_location:
            return False
        dlat = lat - current_location["latitude"]
        dlon = lon - current_location["longitude"]
        distance =  math.sqrt((dlat ** 2) + (dlon ** 2)) * 1.113195e5
        return distance < 1.0

    def _is_abs_altitude_reached(self, target_altitude):
        current_altitude = self._get_global_position()["altitude"]
        return current_altitude >= target_altitude * 0.95

    def _is_global_position_reached(self, lat, lon, alt):
        if self._is_at_target(lat, lon) and self._is_abs_altitude_reached(alt):
            return True
        return False
    
    def _is_heading_reached(self, heading):
        if self._drone(AttitudeChanged(yaw=heading, _policy="check", _float_tol=(1e-3, 1e-1))):
            return True
        return False

    def _is_gimbal_pose_reached(self, yaw, pitch, roll):
        if self._drone(attitude(pitch_absolute=pitch,
            yaw_absolute=yaw, roll_absolute=roll, _policy="check", _float_tol=(1e-3, 1e-1))):
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
        assert self._drone.streaming.stop()
