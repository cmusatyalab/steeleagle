# General imports
import math
import os
import time
import asyncio
import logging
from enum import Enum
# SDK imports (Olympe)
import olympe
from olympe import Drone
from olympe.messages.ardrone3.Piloting import TakeOff, Landing
from olympe.messages.ardrone3.Piloting import PCMD, moveTo, moveBy
from olympe.messages.rth import set_custom_location, return_to_home
from olympe.messages.ardrone3.PilotingState import moveToChanged
from olympe.messages.common.CommonState import BatteryStateChanged
from olympe.messages.ardrone3.PilotingSettingsState import MaxTiltChanged
from olympe.messages.ardrone3.SpeedSettingsState import MaxVerticalSpeedChanged, MaxRotationSpeedChanged
from olympe.messages.ardrone3.PilotingState import AttitudeChanged, GpsLocationChanged, AltitudeChanged, FlyingStateChanged, SpeedChanged
from olympe.messages.ardrone3.GPSState import NumberOfSatelliteChanged
from olympe.messages.gimbal import set_target, attitude
from olympe.messages.wifi import rssi_changed
from olympe.messages.battery import capacity
from olympe.messages.common.CalibrationState import MagnetoCalibrationRequiredState
import olympe.enums.move as move_mode
import olympe.enums.gimbal as gimbal_mode
# Interface import
from quadcopter.quadcopter_interface import QuadcopterItf
# Protocol imports
from protocol import dataplane_pb2 as data_protocol
from protocol import common_pb2 as common_protocol

logger = logging.getLogger(__name__)

class ParrotOlympeDrone(QuadcopterItf):
    
    class FlightMode(Enum):
        LOITER = 1
        TAKEOFF_LAND = 2
        VELOCITY = 3
        GUIDED = 4
        
    def __init__(self, drone_id, **kwargs):
        self.drone_id = drone_id
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
        return "Parrot Drone"

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
            lambda: self._drone(FlyingStateChanged(\
                    state="hovering", _policy="check")\
                    ).success(),
            interval=1
        )
        
        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def land(self):
        await self._switch_mode(ParrotOlympeDrone.FlightMode.TAKEOFF_LAND)
        result = self._drone(Landing()).wait().success()
        
        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def hover(self):
        return await self.set_velocity(0.0, 0.0, 0.0, 0.0)

    async def kill(self):
        return common_protocol.ResponseStatus.NOTSUPPORTED

    async def set_home(self, location):
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude

        result = await self._wait_for_condition(
            lambda: self._drone(set_custom_location(\
                    lat, lng, alt)).wait().success(),
            timeout=5,
            interval=0.1
        )
        
        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED
    
    async def rth(self):
        await self.hover()
        await self._switch_mode(ParrotOlympeDrone.FlightMode.TAKEOFF_LAND)
        self._drone(return_to_home())
        
        return common_protocol.ResponseStatus.COMPLETED
            
    async def set_velocity(self, velocity):
        forward_vel = velocity.forward_vel
        right_vel = velocity.right_vel
        up_vel = velocity.up_vel
        angle_vel = velocity.angle_vel
        
        await self._switch_mode(ParrotOlympeDrone.FlightMode.VELOCITY)

        # Check that the speeds is within the drone bounds
        max_rotation = self._drone.get_state(MaxRotationSpeedChanged)["max"]
        max_vertical_speed = self._drone.get_state(MaxVerticalSpeedChanged)["max"]

        if abs(angle_vel) > max_rotation:
            return common_protocol.ResponseStatus.FAILED
        if abs(up_vel) > max_vertical_speed:
            return common_protocol.ResponseStatus.FAILED

        self._velocity_setpoint = \
                (forward_vel, right_vel, up_vel, angle_vel)
        if self._pid_task is None:
            self._pid_task = asyncio.create_task(\
                    self._velocity_pid())

        return common_protocol.ResponseStatus.COMPLETED

    async def set_global_position(self, location):
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude
        bearing = location.bearing
       
        await self._switch_mode(ParrotOlympeDrone.FlightMode.GUIDED)
        if bearing is None:
            self._drone(
                moveTo(lat, lng, alt, move_mode.orientation_mode.to_target, 0.0)
            )
        else:
            self._drone(
                moveTo(lat, lng, alt, move_mode.orientation_mode.heading_during, bearing)
            )
        
        result = await self._wait_for_condition(
            lambda: self.is_at_target(lat, lon),
            interval=1
        )
        
        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

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

        result = self._drone(moveBy(0.0, 0.0, 0.0, offset))\
                .wait().success()

        if result:
            return common_protocol.ResponseStatus.COMPLETED
        else:
            return common_protocol.ResponseStatus.FAILED

    async def stream_telemetry(self, tel_sock):
        logger.info('Starting telemetry stream')
        # Wait a second to avoid contention issues
        await asyncio.sleep(1) 
        while await self.isConnected():
            try:
                tel_message = data_protocol.Telemetry()
                tel_message.drone_name = self._get_name()
                tel_message.battery = self._get_battery_percentage()
                tel_message.drone_attitude.yaw = self._get_attitude()["yaw"]
                tel_message.drone_attitude.pitch = \
                        self._get_attitude()["pitch"]
                tel_message.drone_attitude.roll = \
                        self._get_attitude()["roll"]
                tel_message.satellites = self._get_satellites()
                tel_message.relative_position.up = self._get_altitude_rel()
                tel_message.global_position.latitude = \
                        self._get_global_position()["latitude"]
                tel_message.global_position.longitude = \
                        self._get_global_position()["longitude"]
                tel_message.global_position.altitude = \
                        self._get_global_position()["altitude"]
                tel_message.global_position.bearing = self._get_heading()
                tel_message.velocity.forward_vel = \
                        self._get_velocity_body()["forward"]
                tel_message.velocity.right_vel = \
                        self._get_velocity_body()["right"]
                tel_message.velocity.up_vel = \
                        self._get_velocity_body()["up"]
                tel_sock.send(tel_message.SerializeToString())
            except Exception as e:
                logger.error(f'Failed to get telemetry, error: {e}')
            await asyncio.sleep(0.01)
                    
    async def stream_video(self, cam_sock):
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
            await asyncio.sleep(0.033)
        self._stop_streaming()
        logger.info("Camera stream ended, disconnected from drone")

    ''' Telemetry methods '''
    def _get_name(self):
        return self.drone_id

    def _get_global_position(self):
        try:
            return (self.drone.get_state(GpsLocationChanged)["latitude"],
                self.drone.get_state(GpsLocationChanged)["longitude"],
                self.drone.get_state(GpsLocationChanged)["altitude"])
        except Exception:
            return None

    def _get_altitude_rel(self):
        return self.drone.get_state(AltitudeChanged)["altitude"]

    def _get_attitude(self):
        att = self.drone.get_state(AttitudeChanged)
        rad_to_deg = 180 / math.pi
        return {"roll": att["roll"] * rad_to_deg, \
                "pitch": att["pitch"] * rad_to_deg, \
                "yaw": att["yaw"] * rad_to_deg}

    def _get_magnetometer(self):
        return common_protocol.ResponseStatus.NOTSUPPORTED

    def _get_battery_percentage(self):
        battery_msg = self._get_cached_message("BATTERY_STATUS")
        if not battery_msg:
            return None
        return battery_msg.battery_remaining

    def _get_satellites(self):
        try:
            return self.drone.get_state(NumberOfSatelliteChanged)["numberOfSatellite"]
        except:
            return None

    def _get_heading(self):
        return self.drone.get_state(AttitudeChanged)["yaw"] * (180 / math.pi)

    def _get_velocity_neu(self):
        ned = self.drone.get_state(SpeedChanged)
        return {"north": ned["speedX"], "east": ned["speedY"], "up": ned["speedZ"] * -1}
        
    def _get_velocity_body(self):
        neu = self._get_velocity_neu()
        vec = np.array([neu["north"], neu["east"]], \
                dtype=float)
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
                "up": neu["up"]}
        return res

    def _get_rssi(self):
        return self.drone.get_state(rssi_changed)["rssi"]

    ''' Coroutine methods '''
    async def _velocity_pid(self):
        try:
            ep = {"forward": 0.0, "right": 0.0, "up": 0.0}
            max_rotation = self._drone.get_state(MaxRotationSpeedChanged)["max"]
            tp = None
            previous_values = None

            def clamp(val, mini, maxi):
                return max(mini, min(val, maxi))

            def update_pid(e, ep, tp, ts, pid_dict):
                P = pid_dict["Kp"] * e
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

            counter = 0
            while self._mode == ParrotOlympeDrone.FlightMode.VELOCITY:
                current = self._get_velocity_body()
                forward_setpoint, right_setpoint, up_setpoint, angular_setpoint = self._velocity_setpoint

                forward = 0
                right = 0
                up = 0

                # Adjust to velocity every 5 ticks
                if counter % 5 == 0:
                    ts = round(time.time() * 1000)

                    error = {}
                    error["forward"] = forward_setpoint - current["forward"]
                    if abs(error["forward"]) < 0.01:
                        error["forward"] = 0
                    error["right"] = right_setpoint - current["right"]
                    if abs(error["right"]) < 0.01:
                        error["right"] = 0
                    error["up"] = up_setpoint - current["up"]
                    if abs(error["up"]) < 0.01:
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
                    counter = 0

                previous_forward = 0
                prev_right = 0
                prev_up = 0
                if previous_values is not None:
                    previous_forward = previous_values["forward"]
                    prev_right = previous_values["right"]
                    prev_up = previous_values["up"]

                forward = int(clamp(forward + previous_forward, -100, 100))
                right = int(clamp(right + prev_right, -100, 100))
                up = int(clamp(up + prev_up, -100, 100))
                ang = int(clamp((angular_setpoint / max_rotation) * 100, -100, 100))

                self._drone(PCMD(1, right, forward, ang, up, timestampAndSeqNum=0))

                if previous_values is None:
                    previous_values = {}
                previous_values["forward"] = forward
                previous_values["right"] = right
                previous_values["up"] = up

                counter += 1

                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            self._forward_pid_values["PrevI"] = 0.0
            self._right_pid_values["PrevI"] = 0.0
            self._up_pid_values["PrevI"] = 0.0
    
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
        
    async def _message_listener(self):
        logger.info("-- Starting message listener")
        try:
            while True:
                msg = await asyncio.to_thread(self.vehicle.recv_match, blocking=True)
                if msg:
                    message_type = msg.get_type()
                    logger.debug(f"Received message type: {message_type}")
        except asyncio.CancelledError:
            logger.info("-- Message listener stopped")
        except Exception as e:
            logger.error(f"-- Error in message listener: {e}")
    
    def _get_cached_message(self, message_type):
        try:
            logger.debug(f"Currently connection message types: {list(self.vehicle.messages)}")
            return self.vehicle.messages[message_type]
        except KeyError:
            logger.error(f"Message type {message_type} not found in cache")
            return None
        
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
    async def _start_streaming(self):
        self._streaming_thread = PDRAWStreamingThread(self._drone)
        self._streaming_thread.start()

    async def _get_video_frame(self):
        if self._streaming_thread:
            return self._streaming_thread.grab_frame().tobytes()

    async def _stop_streaming(self):
        self._streaming_thread.stop()


# Streaming imports
import threading
import queue

class PDRAWStreamingThread(threading.Thread):

    def __init__(self, drone):
        threading.Thread.__init__(self)
        self._drone = drone
        self._frame_queue = queue.Queue()
        self._current_frame = np.zeros((720, 1280, 3), np.uint8)

        self.drone.streaming.set_callbacks(
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
