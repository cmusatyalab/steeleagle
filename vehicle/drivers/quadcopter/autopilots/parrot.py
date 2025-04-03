# General imports
import math
import os
import time
import asyncio
from enum import Enum
import logging
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

class ParrotDrone(QuadcopterItf):
    
    class FlightMode(Enum):
        LOITER = 1
        TAKEOFF_LAND = 2
        VELOCITY = 3
        GUIDED = 4
        
    def __init__(self, drone_id, **kwargs):
        self.drone_id = drone_id
        self.ip = None
        if "ip" in kwargs:
            self.ip = kwargs["ip"]
        # Create the drone object
        self._drone = Drone(self.ip)
        # Drone flight modes and setpoints
        self._attitude_setpoint = None
        self._velocity_setpoint = None
        self._pid_task = None
        self._mode = ParrotDrone.FlightMode.LOITER

    ''' Interface methods '''
    async def get_type(self):
        return "Parrot Drone"

    async def connect(self, connection_string):
        # Connect to drone
        return self._drone.connect()
        
    async def is_connected(self):
        return self._drone.connection_state()

    async def disconnect(self):
        self._drone.disconnect()
    
    async def take_off(self):
        await self._switch_mode(ParrotDrone.FlightMode.TAKEOFF_LAND)
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
        await self._switch_mode(ParrotDrone.FlightMode.TAKEOFF_LAND)
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
        await self._switch_mode(ParrotDrone.FlightMode.TAKEOFF_LAND)
        self._drone(return_to_home())
        
        return common_protocol.ResponseStatus.COMPLETED
            
    async def set_velocity(self, velocity):
        forward_vel = velocity.forward_vel
        right_vel = velocity.right_vel
        up_vel = velocity.up_vel
        angle_vel = velocity.angle_vel
        
        await self._switch_mode(ParrotDrone.FlightMode.VELOCITY)

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
                    self._velocityPID())

        return common_protocol.ResponseStatus.COMPLETED

    async def set_global_position(self, location):
        await self.set_bearing(location)
        lat = location.latitude
        lon = location.longitude
        alt = location.altitude
        bearing = location.bearing
       
        await self._switch_mode(ParrotDrone.FlightMode.GUIDED)
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
        result =  await self._wait_for_condition(
            lambda: self._is_bearing_reached(bearing),
            interval=0.5
        )
        
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
        return common_protocol.ResponseStatus.NOTSUPPORTED
    
    ''' Connect methods '''
    def _request_message_interval(self, message_id: int, frequency_hz: float):
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system, self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
            message_id,
            1e6 / frequency_hz,
            0, 0, 0, 0,
            0, 
        )

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
        neu = await self._get_velocity_neu()
        vec = np.array([neu["north"], neu["east"]], \
                dtype=float)
        vecf = np.array([0.0, 1.0], dtype=float)

        hd = (await self.getHeading()) + 90
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
                "up": NEU["up"]}
        return res

    def _get_rssi(self):
        return self.drone.get_state(rssi_changed)["rssi"]

    ''' Coroutine methods '''
    async def _setpoint_heartbeat(self):
        if await self._switch_mode(PX4Drone.FlightMode.OFFBOARD) == False:
            logger.error("Failed to set mode to GUIDED")
            return
        
        # Send frequent setpoints to keep the drone in offboard mode.
        while True:
            if self.offboard_mode == PX4Drone.OffboardHeartbeatMode.VELOCITY:
                self.vehicle.mav.set_position_target_local_ned_send(
                    0,
                    self.vehicle.target_system,
                    self.vehicle.target_component,
                    mavutil.mavlink.MAV_FRAME_BODY_NED,
                    0b010111000111,
                    0, 0, 0,
                    self._setpoint[0], self._setpoint[1], -self._setpoint[2],
                    0, 0, 0,
                    0, self._setpoint[3]
                )
            elif self.offboard_mode == PX4Drone.OffboardHeartbeatMode.RELATIVE:
                pass
            elif self.offboard_mode == PX4Drone.OffboardHeartbeatMode.GLOBAL:
                self.vehicle.mav.set_position_target_global_int_send(
                    0,
                    self.vehicle.target_system,
                    self.vehicle.target_component,
                    mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                    0b0000111111111000,
                    int(self._setpoint[0] * 1e7),
                    int(self._setpoint[1] * 1e7),
                    self._setpoint[2],
                    0, 0, 0,
                    0, 0, 0,
                    0, 0
                )
            await asyncio.sleep(0.05)

    ''' Actuation methods '''
    async def _arm(self):
        logger.info("-- Arming")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1,
            0, 0, 0, 0, 0, 0
        )
        logger.info("-- Arm command sent")


        result =  await self._wait_for_condition(
            lambda: self.is__armed(),
            timeout=5,
            interval=1
        )
        
        if result:
            logger.info("-- Armed successfully")
        else:
            logger.error("-- Arm failed")
        return result

    async def _disarm(self):
        logger.info("-- Disarming")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system,
            self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            0,
            0, 0, 0, 0, 0, 0
        )
        logger.info("-- Disarm command sent")

        result =  await self._wait_for_condition(
            lambda: self.is_disarmed(),
            timeout=5,
            interval=1
        )
        
        if result:
            self.mode = None
            logger.info("-- Disarmed successfully")
        else:
            logger.error("-- Disarm failed")
            
        return result  

    async def _switch_mode(self, mode):
        mode_target = mode.value
        curr_mode = self.mode.value if self.mode else None
        
        if self.mode == mode:
            logger.info(f"Already in mode {mode_target}")
            return True
        
        # switch mode
        if mode_target not in self._mode_mapping:
            logger.info(f"Mode {mode_target} not supported!")
            return False
        
        mode_id = self._mode_mapping[mode_target]
        logger.info(f"Mode ID Triplet: {mode_id}")
        self.vehicle.mav.command_long_send(
            self.vehicle.target_system, self.vehicle.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE, 0,
            mode_id[0], mode_id[1], mode_id[2], 0, 0, 0, 0)
        
        if mode is not PX4Drone.FlightMode.OFFBOARD:
            result = await self._wait_for_condition(
                lambda: self.is_mode_set(mode),
                timeout=5,
                interval=1
            )
            
            if result:
                self.mode = mode
                logger.info(f"Mode switched to {mode_target}")

            return result
        else:
            logger.info(f"Priming for OFFBOARD mode")
            return True
        
    ''' ACK methods '''    
    def _is_home_set(self):
        msg = self.vehicle.recv_match(type='COMMAND_ACK', blocking=True)
        return msg and msg.command == mavutil.mavlink.MAV_CMD_DO_SET_HOME \
                and msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED

    def _is_altitude_reached(self, target_altitude):
        current_altitude = self._get_altitude_rel()
        return current_altitude >= target_altitude * 0.95
    
    def _is_bearing_reached(self, bearing):
        logger.info(f"Checking if bearing is reached: {bearing}")
        attitude = self._get_attitude()
        if not attitude:
            return False  # Return False if attitude data is unavailable

        current_yaw = (math.degrees(attitude["yaw"]) + 360) % 360
        target_yaw = (bearing + 360) % 360
        return abs(current_yaw - target_yaw) <= 2
    
    def _is_at_target(self, lat, lon):
        current_location = self._get_global_position()
        if not current_location:
            return False
        dlat = lat - current_location["latitude"]
        dlon = lon - current_location["longitude"]
        distance =  math.sqrt((dlat ** 2) + (dlon ** 2)) * 1.113195e5
        return distance < 1.0
        
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
                logger.error("-- Timeout waiting for condition")
                return False
            await asyncio.sleep(interval)


# Streaming imports
import threading
import queue

class PDRAWStreamingThread(threading.Thread):

    def __init__(self, drone, ip):
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

    def _grab_frame(self):
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
