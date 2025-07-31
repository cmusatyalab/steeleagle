import asyncio
import logging
import time
import numpy as np
from typing import Optional

import common_pb2 as common_protocol

logger = logging.getLogger(__name__)
M_PER_LAT_DEG = 111139
LANDED_DRAIN_RATE = .03
ACTIVE_DRAIN_RATE = .06
MAX_SPEED = 15 # m/s
MAX_CLIMB = 4 # m/s
MAX_ACCELERATION = 10 # m/s^2
MAX_ROTA_RATE = 250
MAX_YAW_RATE = 180
MAX_G_ROTA_RATE = 300
LATERAL_BRAKE_THRESHOLD = MAX_SPEED * 1.5
VERTICAL_BRAKE_THRESHOLD = MAX_CLIMB * 1.5
MATCH_TOLERANCE = .001
DEG_MATCH_TOLERANCE = .00003 # ~3m error in degrees of lat
ALT_MATCH_TOLERANCE = .05 # m
TICK_COUNT = 60
TICK_RATE = 1 / TICK_COUNT
DEFAULT_LAT = 40.41368353053923
DEFAULT_LON = -79.9489233699767
DEFAULT_ALT = 0
DEFAULT_SAT_COUNT = 16
TASK_TIMEOUT = 10 # value in seconds

class SimulatedDrone():
    def __init__(self, ip, drone_id="Simulated Drone", lat=DEFAULT_LAT, lon=DEFAULT_LON, alt=DEFAULT_ALT, takeoff_alt=10, mag_interference=0):
        self._device_type = "Digital Drone"
        self.connection_ip = ip
        self._active_connection = False
        self._takeoff_alt = takeoff_alt
        self._state = {}
        self.set_name(drone_id)
        self._initialize_internal_dicts()
        self.set_current_position(lat, lon, alt)
        self.set_magnetometer(mag_interference)

    def _initialize_internal_dicts(self) -> None:
        self.current_position: dict[str, Optional[float]] = {
            "lat": None,
            "lon": None,
            "alt": None
        }
        self._position_target: dict[str, Optional[float]] = {
            "lat": None,
            "lon": None,
            "alt": None
        }
        self._pose_target: dict[str, Optional[float]] = {
            "pitch": None,
            "roll": None,
            "yaw": None
        }
        self._gimbal_target: dict[str, Optional[float]] = {
            "g_pitch": None,
            "g_roll": None,
            "g_yaw": None
        }
        self._velocity_target: dict[str, Optional[float]] = {
            "speedX": None,
            "speedY": None,
            "speedZ": None
        }
        self._pending_action = False
        self._active_action = False
        self._position_flag = False
        self.set_velocity(0, 0, 0)
        self.set_attitude(0, 0, 0)
        self.set_gimbal_pose(0, 0, 0)
        self._set_acceleration(0, 0, 0)
        self._set_drone_rotation(0, 0, 0)
        self._set_gimbal_rotation(0, 0, 0)
        self.set_battery_percent(100)
        self.set_satellites(DEFAULT_SAT_COUNT)

    async def state_loop(self):
        while self._active_connection:
            if self._pending_action:
                if self._active_action:
                    self._cancel_current_action()
                else:
                    # Start accelerating in proper direction only after previous task canceled
                    if self._check_target_active("position"):
                        self._calculate_acceleration_direction()
                        self._active_action = True
                        self._pending_action = False
                    # Update flags when no position target is set as part of gimbal rotation
                    if self._check_target_active("gimbal"):
                        self._active_action = True
                        self._pending_action = False
            if self._check_target_active("velocity"):
                self._check_velocity_reached()
                if not self._check_target_active("position"):
                    self._zero_velocity()
            if self._check_target_active("position"):
                self._check_braking_thresholds()
            if self._check_target_active("pose"):
                self._check_drone_pose_reached()
            if self._check_target_active("gimbal"):
                self._check_gimbal_pose_reached()
            self._update_kinematics()
            time_elapsed = self.t_current - self.t_last
            self.t_last = self.t_current
            logger.info(f"{time_elapsed} since last loop iteration")
            await asyncio.sleep(TICK_RATE - time_elapsed)
        logger.info("Connection terminated, shutting down...")

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

    def _cancel_current_action(self):
        self._zero_velocity()
        if self._check_target_active("gimbal"):
            self._set_gimbal_rotation(0, 0, 0)
            self._set_gimbal_target(None, None, None)
        if self._check_target_active("pose"):
            self._set_drone_rotation(0, 0, 0)
            self._set_pose_target(None, None, None)
        
        if self.get_current_position()[2] is not None and self.get_current_position()[2] > 0:
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
        else:
            self.set_flight_state(common_protocol.FlightStatus.IDLE)
        self._active_action = None

    async def _register_pending_task(self):
        if self._pending_action:
            return False
        self._pending_action = True
        
        return await self._wait_for_condition(lambda: self._is_task_lock_open(), timeout=TASK_TIMEOUT, interval=.5)

    """ Connectivity Methods """

    def connect(self) -> bool:
        if self._active_connection == False:
            self._active_connection = True
            logger.info("Connection established with simulated digital drone...")
            logger.info("Starting internal state loop...")
            self.t_current = time.time()
            self.t_last = self.t_current
            self._loop = asyncio.new_event_loop()
            self._loop.create_task(self.state_loop())
            logger.info("Internal state loop active...")
            return True
        logger.warning("Attempted multiple connections on simulated drone object...")
        return False

    def connection_state(self) -> bool:
        return self._active_connection
    
    def disconnect(self) -> bool:
        if self._active_connection:
            self._active_connection = False
            self._loop.close()
            logger.info("Disconnected from simulated digital drone...")
            return True
        logger.warning("Attempted to disconnect without active connection to simulated drone...")
        return False
    
    """ Operational Methods """

    async def take_off(self):
        if (not self.check_flight_state(common_protocol.FlightStatus.LANDED)
            and not self.check_flight_state(common_protocol.FlightStatus.IDLE)):
            logger.error(f"take_off: {self.get_state("drone_id")} unable to execute take off command when not landed...")
            logger.error(f"Current flight state: {self.get_state("flight_state")}")
        
        result = await self._register_pending_task()
        if not result:
            logger.warning("Pending task already queued, unable to register take off command")
            return
        
        self.set_flight_state(common_protocol.FlightStatus.TAKING_OFF)
        current_position = self.get_current_position()
        self._set_position_target(current_position[0], current_position[1], self._takeoff_alt)

        result = await self._wait_for_condition(lambda: self.is_takeoff_complete(), timeout=TASK_TIMEOUT)
        if result:
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
            self._active_action = False
            logger.info(f"{self.get_state("drone_id")} completed takeoff...")
        else:
            self._zero_velocity()
            self.set_flight_state(common_protocol.FlightStatus.IDLE)
            self._active_action = False
            logger.warning(f"{self.get_state("drone_id")} failed to take off...")

    async def land(self):
        if (self.check_flight_state(common_protocol.FlightStatus.LANDED)
            or self.check_flight_state(common_protocol.FlightStatus.LANDING)
            or self.check_flight_state(common_protocol.FlightStatus.IDLE)):
            logger.warning(f"land: {self.get_state("drone_id")} already landed. Ignoring command...")

        await self._register_pending_task()
        self.set_flight_state(common_protocol.FlightState.LANDING)
        self._zero_velocity()
        current_position = self.get_current_position()
        self._set_position_target(current_position[0], current_position[1], 0)

        result = await self._wait_for_condition(lambda: self.is_landed(), timeout=TASK_TIMEOUT)
        if result:
            self.set_flight_state(common_protocol.FlightStatus.LANDED)
            self._active_action = False
            logger.info(f"{self.get_state("drone_id")} completed landing...")
        else:
            self._zero_velocity()
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
            self._active_action = False
            current_position = self.get_current_position()
            logger.warning(f"{self.get_state("drone_id")} failed to land...")
            logger.warning(f"Current position after failed attempt: ({current_position[0]}, "
                           f"{current_position[1]}, {current_position[2]})")

    async def move_to(self, lat, lon, altitude, heading_mode, bearing):
        if (self.check_flight_state(common_protocol.FlightStatus.LANDED)
            or self.check_flight_state(common_protocol.FlightStatus.LANDING)
            or self.check_flight_state(common_protocol.FlightStatus.IDLE)):
            logger.warning(f"move_to: {self.get_state("drone_id")} unable to execute move command"
                           "from ground. Take off first...")
        
        await self._register_pending_task()
        self._zero_velocity()
        
        if heading_mode == common_protocol.LocationHeadingMode.TO_TARGET:
            # Orients drone to fixed target bearing
            self._set_pose_target(None, None, bearing)
        else:
            # Orients drone along the flight path heading (face 'forward')
            self._set_pose_target(None, None, self.calculate_bearing(lat, lon))

        self._set_position_target(lat, lon, altitude)
        self.set_flight_state(common_protocol.FlightStatus.MOVING)

        result = await self._wait_for_condition(lambda: self._check_position_reached(), timeout=None)
        current_position = self.get_current_position()
        if result:
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
            self._active_action = False
            logger.info(f"{self.get_state("drone_id")} completed movement to position "
                        f"({current_position[0]}, {current_position[1]}, {current_position[2]})")
        else:
            self._zero_velocity()
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
            self._active_action = False
            logger.warning(f"{self.get_state("drone_id")} failed to move to target position ({lat}, {lon}, {altitude})...")
            logger.warning(f"Current position: ({current_position[0]}, {current_position[1]}, {current_position[2]})")

    async def extended_move_to(self, lat, lon, altitude, heading_mode, bearing, lateral_vel, up_vel, angular_vel):
        if (self.check_flight_state(common_protocol.FlightStatus.LANDED)
            or self.check_flight_state(common_protocol.FlightStatus.LANDING)
            or self.check_flight_state(common_protocol.FlightStatus.IDLE)):
            logger.warning(f"move_to: {self.get_state("drone_id")} unable to execute move command"
                           "from ground. Take off first...")
        
        await self._register_pending_task()
        self._zero_velocity()
        path_heading = self.calculate_bearing(lat, lon)

        if heading_mode == common_protocol.LocationHeadingMode.TO_TARGET:
            # Orients drone to fixed target bearing
            self._set_pose_target(None, None, bearing)
        else:
            # Orients drone along the flight path heading (face 'forward')
            self._set_pose_target(None, None, path_heading)

        x_vel, y_vel = self.partition_lateral_velocity(lateral_vel, path_heading)
        self._set_position_target(lat, lon, altitude)
        self._set_velocity_target(x_vel, y_vel, up_vel)
        self.set_flight_state(common_protocol.FlightStatus.MOVING)

        result = await self._wait_for_condition(lambda: self._check_position_reached(), timeout=None)
        current_position = self.get_current_position()
        if result:
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
            self._active_action = False
            logger.info(f"{self.get_state("drone_id")} completed movement to position "
                        f"({current_position[0]}, {current_position[1]}, {current_position[2]})")
        else:
            self._zero_velocity()
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
            self._active_action = False
            logger.warning(f"{self.get_state("drone_id")} failed extended move to target position ({lat}, {lon}, {altitude})...")
            logger.warning(f"Current position: ({current_position[0]}, {current_position[1]}, {current_position[2]})")

    async def set_target(self, gimbal_id, control_mode, pitch, roll, yaw):
        # position, velocity
        if control_mode == "velocity":
            logger.info("Gimbal rotation without target not implemented")
            return
        
        await self._register_pending_task()
        if control_mode == "position":
            self._set_gimbal_target(pitch, roll, yaw)

        result = await self._wait_for_condition(lambda: self._check_gimbal_pose_reached(), timeout=TASK_TIMEOUT)
        current_g_pose = self.get_state("gimbal_pose")
        if result:
            self._active_action = False
            logger.info(f"{self.get_state("drone_id")} completed aligning gimbal {gimbal_id} to target. "
                        f"Pitch: {current_g_pose["g_pitch"]}, Roll: {current_g_pose["g_roll"]}, Yaw: {current_g_pose["yaw"]}")
        else:
            self._active_action = False
            logger.warning(f"{self.get_state("drone_id")} failed to align gimbal {gimbal_id} to target. "
                           f"Pitch: {current_g_pose["g_pitch"]}, Roll: {current_g_pose["g_roll"]}, Yaw: {current_g_pose["yaw"]}")

    def set_home_location(self, lat, lon, alt):
        self.home_location = {
            "lat": lat,
            "lon": lon,
            "alt": alt
        }
        logger.info(f"Home location updated to ({lon}, {lat}) at elevation {alt}...")

    def _update_state(self, characteristic: str, value):
        if characteristic not in self._state:
            logger.info(f"Adding {characteristic} to internal state...")
        self._state[characteristic] = value

    """ Utility methods """

    def check_flight_state(self, target_state):
        if target_state == self.get_state("flight_state"):
            return True
        return False
    
    def _check_target_active(self, target_type: str):
        match target_type:
            case "position":
                target = self._position_target
            case "velocity":
                target = self._velocity_target
            case "pose":
                target = self._pose_target
            case "gimbal":
                target = self._gimbal_target
            case _:
                logger.error(f"_check_target_active: Invalid target type requested. Received {target_type}...")
                return
        return any(value is not None for value in target.values())
    
    def get_current_position(self) -> tuple[Optional[float], Optional[float], Optional[float]]:
        try:
            return (
                self.current_position["lat"],
                self.current_position["lon"],
                self.current_position["alt"]
            )
        except:
            logger.error("Unable to retrieve current position...")
            return (None, None, None)

    def get_home_location(self):
        try:
            return (
                self.home_location["lat"],
                self.home_location["lon"],
                self.home_location["alt"]
            )
        except:
            logger.error("Home location not set...")
            return None
        
    def get_state(self, characteristic: str):
        if characteristic not in self._state:
            logger.error(f"{characteristic} not included in drone state. Unable to retrieve...")
            return None
        return self._state[characteristic]
    
    def is_stopped(self):
        current_velocity = self.get_state("velocity")
        if (current_velocity == None 
            or current_velocity["speedX"] != 0
            or current_velocity["speedY"] != 0
            or current_velocity["speedZ"] != 0
        ):
            return False
        return True


    def is_takeoff_complete(self):
        return (self._check_position_reached()
                and self.is_stopped()
                and self.check_flight_state(common_protocol.FlightStatus.TAKING_OFF))

    def is_task_lock_open(self):
        # Checks if the main event loop has moved the registered task from pending to active
        return not self._pending_action

    """ Internal State Methods """

    def set_attitude(self, pitch: float, roll: float, yaw: float):
        attitude = {
            "pitch": pitch,
            "roll": roll,
            "yaw": yaw
        }
        self._update_state("attitude", attitude)
        logger.debug(f"Drone attitude set to pitch: {pitch}, roll: {roll}, yaw: {yaw}")
    
    def set_battery_percent(self, starting_charge: float):
        self._update_state("battery_percent", starting_charge)

    def set_current_position(self, new_lat: float, new_lon: float, new_alt: float):
        self.current_position.update(
            lat=new_lat,
            lon=new_lon,
            alt=new_alt
        )
        logger.debug(f"Current position set to ({new_lat}, {new_lon}, {new_alt})")

    # flight_state expected to be common_protocol.FlightStatus member
    def set_flight_state(self, flight_state):
        self._update_state("flight_state", flight_state)
        logger.debug(f"Current flight state set to: {flight_state}")

    def set_gimbal_pose(self, pitch: float, roll: float, yaw: float):
        gimbal_pose = {
            "g_pitch": pitch,
            "g_roll": roll,
            "g_yaw": yaw
        }
        self._update_state("gimbal_pose", gimbal_pose)
        logger.debug(f"Gimbal pose set to g_pitch: {pitch}, g_roll: {roll}, g_yaw: {yaw}")

    def set_magnetometer(self, condition_code: int):
        # 0 for good, 1 for calibration, 2 for perturbation
        self._update_state("magnetometer", condition_code)
        logger.debug(f"Magnetometer reading updated to {condition_code}")

    def set_name(self, drone_id: str):
        self._update_state("drone_id", drone_id)
        logger.debug(f"Drone name set as: {drone_id}")

    def set_velocity(self, vel_x: float, vel_y: float, vel_z: float):
        velocity = {
            "speedX": max(min(vel_x, MAX_SPEED), -MAX_SPEED),
            "speedY": max(min(vel_y, MAX_SPEED), -MAX_SPEED),
            "speedZ": max(min(vel_z, MAX_CLIMB), -MAX_CLIMB)
        }
        self._update_state("velocity", velocity)
        logger.debug(f"Drone velocity set to ({vel_x}, {vel_y}, {vel_z})")
    
    def set_satellites(self, satellite_count: int):
        self._update_state("satellite_count", satellite_count)
        logger.debug(f"GPS satellite count set to: {satellite_count}")
    
    """ Kinematics """

    def _calculate_acceleration_direction(self):
        current_position = self.get_current_position()
        if (self._position_target["lat"] == None
            or self._position_target["lon"] == None
            or self._position_target["alt"] == None):
            logger.error("Position target not set...")
            logger.error(f"Target lat: {self._position_target["lat"]}")
            logger.error(f"Target lon: {self._position_target["lon"]}")
            logger.error(f"Target alt: {self._position_target["alt"]}")
            return
        if (current_position[0] == None
            or current_position[1] == None
            or current_position[2] == None):
            logger.error("Current position not set...")
            logger.error(f"Current lat: {current_position[0]}")
            logger.error(f"Current lon: {current_position[1]}")
            logger.error(f"Current alt: {current_position[2]}")
            return 
        else:
            if self._position_target["lat"] - current_position[0] > 0:
                acc_x = MAX_ACCELERATION
            else:
                acc_x = -MAX_ACCELERATION
            if self._position_target["lon"] - current_position[1] > 0:
                acc_y = MAX_ACCELERATION
            else:
                acc_y = -MAX_ACCELERATION
            if self._position_target["alt"] - current_position[2] > 0:
                acc_z = MAX_CLIMB
            else:
                acc_z = -MAX_CLIMB

            self._set_acceleration(acc_x, acc_y, acc_z)
            logger.debug(f"_calculate_acceleration_direction: Acceleration set to "
                         f"({acc_x}, {acc_y}, {acc_z})")

    def calculate_bearing(self, lat: float, lon: float) -> Optional[float]:
        current_position = self.get_current_position()
        if (current_position[0] == None
            or current_position[1] == None
            or current_position[2] == None):
            logger.error("calculate_bearing: Current position invalidly set...")
            logger.error(f"Current lat: {current_position[0]}")
            logger.error(f"Current lon: {current_position[1]}")
            logger.error(f"Current alt: {current_position[2]}")
            return None
        start_lat = np.deg2rad(current_position[0])
        start_lon = np.deg2rad(current_position[1])
        end_lat = np.deg2rad(lat)
        end_lon = np.deg2rad(lon)
        d_lon = end_lon - start_lon
        theta = np.atan2(np.sin(d_lon) * np.cos(end_lat),
                         np.cos(start_lat) * np.sin(end_lat) - np.sin(start_lat) * np.cos(end_lat) * np.cos(d_lon))
        result = (np.rad2deg(theta) + 360) % 360
        return result



    def _calculate_deceleration(self, vel_val: float, dist_remaining: float):
        # Used for immediate stops that do not include a position target
        if dist_remaining == 0:
            return -vel_val
        elif vel_val < 0:
            return (vel_val**2) / (2 * dist_remaining)
        else:
            return -(vel_val**2) / (2 * dist_remaining)
        
    def _check_braking_thresholds(self):
        acceleration = self.get_state("acceleration")
        velocity = self.get_state("velocity")
        current_position = self.get_current_position()

        if acceleration == None or velocity == None:
            logger.error("Failed to retrieve drone velocity and acceleration")
            logger.error(f"Velocity: {velocity}")
            logger.error(f"Acceleration: {acceleration}")
            return
        logger.debug(f"_check_braking_thresholds: Starting acceleration: "
                     f"({acceleration["accX"]}, {acceleration["accY"]}, {acceleration["accZ"]})")
        if (self._position_target["lat"] == None
            or self._position_target["lon"] == None
            or self._position_target["alt"] == None):
            logger.error("Position target not set...")
            logger.error(f"Target lat: {self._position_target["lat"]}")
            logger.error(f"Target lon: {self._position_target["lon"]}")
            logger.error(f"Target alt: {self._position_target["alt"]}")
            return
        if (current_position[0] == None
            or current_position[1] == None
            or current_position[2] == None):
            logger.error("Current position not set...")
            logger.error(f"Current lat: {current_position[0]}")
            logger.error(f"Current lon: {current_position[1]}")
            logger.error(f"Current alt: {current_position[2]}")
            return 

        dist_x = self._position_target["lat"] - current_position[0]
        dist_y = self._position_target["lon"] - current_position[1]
        dist_z = self._position_target["alt"] - current_position[2]
        if abs(dist_x) <= LATERAL_BRAKE_THRESHOLD:
            acceleration["accX"] = self._calculate_deceleration(velocity["speedX"], dist_x)
        if abs(dist_y) <= LATERAL_BRAKE_THRESHOLD:
            acceleration["accY"] = self._calculate_deceleration(velocity["speedY"], dist_y)
        if abs(dist_z) <= VERTICAL_BRAKE_THRESHOLD:
            acceleration["accZ"] = self._calculate_deceleration(velocity["speedZ"], dist_z)
        self._set_acceleration(acceleration["accX"], acceleration["accY"], acceleration["accZ"])
        logger.debug(f"_check_braking_thresholds: Acceleration after braking checks: "
                     f"({acceleration["accX"]}, {acceleration["accY"]}, {acceleration["accZ"]})")

    def _check_drone_pose_reached(self):
        pose = self.get_state("attitude")
        if (pose == None
            or pose["pitch"] == None
            or pose["roll"] == None
            or pose["yaw"] == None):
            logger.error("Failed to retrieve current drone pose...")
            logger.error(f"Pose: {pose}")
            return
        if (self._pose_target["pitch"] == None
            or self._pose_target["roll"] == None
            or self._pose_target["yaw"] == None):
            logger.error("Pose target not properly set...")
            logger.error(f"Pitch: {self._pose_target["pitch"]}")
            logger.error(f"Roll: {self._pose_target["roll"]}")
            logger.error(f"Yaw: {self._pose_target["yaw"]}")
            return

        if (abs(self._pose_target["pitch"] - pose[0]) <= MATCH_TOLERANCE
            and abs(self._pose_target["roll"] - pose[1]) <= MATCH_TOLERANCE
            and abs(self._pose_target["yaw"] - pose[2]) <= MATCH_TOLERANCE):
            self._set_drone_rotation(0, 0, 0)
            self._pose_target.update(
                pitch=None,
                roll=None,
                yaw=None
            )

    def _check_gimbal_pose_reached(self):
        g_pose = self.get_state("gimbal_pose")
        if (g_pose == None
            or g_pose["g_pitch"] == None
            or g_pose["g_roll"] == None
            or g_pose["g_yaw"] == None):
            logger.error("Failed to retrieve current gimbal pose...")
            logger.error(f"Gimbal pose: {g_pose}")
            return False
        if (self._gimbal_target["g_pitch"] == None
            or self._gimbal_target["g_roll"] == None
            or self._gimbal_target["g_yaw"] == None):
            logger.error("Gimbal pose target not properly set...")
            logger.error(f"Gimbal pitch: {self._gimbal_target["g_pitch"]}")
            logger.error(f"Gimbal roll: {self._gimbal_target["g_roll"]}")
            logger.error(f"Gimbal yaw: {self._gimbal_target["g_yaw"]}")
            return False
        
        if (abs(self._gimbal_target["g_pitch"] - g_pose["g_pitch"]) <= MATCH_TOLERANCE
            and abs(self._gimbal_target["g_roll"] - g_pose["g_roll"]) <= MATCH_TOLERANCE
            and abs(self._gimbal_target["g_yaw"] - g_pose["g_yaw"]) <= MATCH_TOLERANCE):
            self._set_gimbal_rotation(0, 0, 0)
            self._gimbal_target.update(
                g_pitch=None,
                g_roll=None,
                g_yaw=None
            )
            return True
        return False

    def _check_position_reached(self):
        # Check for previous call clearing position target
        if self._position_flag:
            return True
        current_position = self.get_current_position()

        if (self._position_target["lat"] == None
            or self._position_target["lon"] == None
            or self._position_target["alt"] == None):
            logger.error("_check_position_reached: Position target not set...")
            logger.error(f"Target lat: {self._position_target["lat"]}")
            logger.error(f"Target lon: {self._position_target["lon"]}")
            logger.error(f"Target alt: {self._position_target["alt"]}")
            return False
        if (current_position[0] == None
            or current_position[1] == None
            or current_position[2] == None):
            logger.error("_check_position_reached: Current position not set...")
            logger.error(f"Current lat: {current_position[0]}")
            logger.error(f"Current lon: {current_position[1]}")
            logger.error(f"Current alt: {current_position[2]}")
            return False

        if (abs(current_position[0] - self._position_target["lat"]) <= DEG_MATCH_TOLERANCE
            and abs(current_position[1] - self._position_target["lon"]) <= DEG_MATCH_TOLERANCE
            and abs(current_position[2] - self._position_target["alt"]) <= ALT_MATCH_TOLERANCE):
            self.set_current_position(
                self._position_target["lat"],
                self._position_target["lon"],
                self._position_target["alt"]
            )
            self._zero_velocity()
            self._position_flag = True
            return True
        return False

    def _check_velocity_reached(self):
        velocity = self.get_state("velocity")
        acceleration = self.get_state("acceleration")

        if acceleration == None or velocity == None:
            logger.error("Failed to retrieve drone velocity and acceleration")
            logger.error(f"Velocity: {velocity}")
            logger.error(f"Acceleration: {acceleration}")
            return
        vel_x = velocity["speedX"]
        vel_y = velocity["speedY"]
        vel_z = velocity["speedZ"]

        if (vel_x == None or vel_y == None or vel_z == None):
            logger.error("Drone velocity not properly set...")
            logger.error(f"Drone x velocity: {vel_x}")
            logger.error(f"Drone y velocity: {vel_y}")
            logger.error(f"Drone z velocity: {vel_z}")
            return
        if (self._velocity_target["speedX"] == None
            or self._velocity_target["speedY"] == None
            or self._velocity_target["speedZ"] == None):
            logger.error("Velocity target not properly set...")
            logger.error(f"Velocity speedX: {self._velocity_target["speedX"]}")
            logger.error(f"Velocity speedY: {self._velocity_target["speedY"]}")
            logger.error(f"Velocity speedZ: {self._velocity_target["speedZ"]}")
            return

        if abs(vel_x - self._velocity_target["speedX"]) <= MATCH_TOLERANCE:
            acceleration["accX"] = 0
        if abs(vel_y - self._velocity_target["speedY"]) <= MATCH_TOLERANCE:
            acceleration["accY"] = 0
        if abs(vel_z - self._velocity_target["speedZ"]) <= MATCH_TOLERANCE:
            acceleration["accZ"] = 0
        # If all velocity targets are achieved, delete the current velocity target
        if acceleration["accX"] == 0 and acceleration["accY"] == 0 and acceleration["accZ"] == 0:
            self._set_velocity_target(None, None, None)
        self._set_acceleration(acceleration["accX"], acceleration["accY"], acceleration["accZ"])

    def _set_acceleration(self, accX: float, accY: float, accZ: float):
        acceleration = {
            "accX": max(min(accX, MAX_ACCELERATION), -MAX_ACCELERATION),
            "accY": max(min(accY, MAX_ACCELERATION), -MAX_ACCELERATION),
            "accZ": max(min(accZ, MAX_ACCELERATION), -MAX_ACCELERATION)
        }
        self._update_state("acceleration", acceleration)

    def _set_drone_rotation(self, pitch_rate: float, roll_rate: float, yaw_rate: float):
        rotation = {
            "pitch_rate": max(min(pitch_rate, MAX_ROTA_RATE), -MAX_ROTA_RATE),
            "roll_rate": max(min(roll_rate, MAX_ROTA_RATE), -MAX_ROTA_RATE),
            "yaw_rate": max(min(yaw_rate, MAX_YAW_RATE), -MAX_YAW_RATE)
        }
        self._update_state("drone_rotation_rates", rotation)

    def _set_gimbal_rotation(self, g_pitch_rate: float, g_roll_rate: float, g_yaw_rate: float):
        rotation = {
            "g_pitch_rate": max(min(g_pitch_rate, MAX_G_ROTA_RATE), -MAX_G_ROTA_RATE),
            "g_roll_rate": max(min(g_roll_rate, MAX_G_ROTA_RATE), -MAX_G_ROTA_RATE),
            "g_yaw_rate": max(min(g_yaw_rate, MAX_G_ROTA_RATE), -MAX_G_ROTA_RATE)
        }
        self._update_state("gimbal_rotation_rates", rotation)
    
    def _set_gimbal_target(self, new_g_pitch: Optional[float], new_g_roll: Optional[float], new_g_yaw: Optional[float]):
        current_g_pose = self.get_state("gimbal_pose")
        if any([new_g_pitch, new_g_roll, new_g_yaw]):
            if new_g_pitch == None:
                target_g_pitch = current_g_pose["g_pitch"]
            else:
                target_g_pitch = new_g_pitch
            if new_g_roll == None:
                target_g_roll = current_g_pose["g_roll"]
            else:
                target_g_roll = new_g_roll
            if new_g_yaw == None:
                target_g_yaw = current_g_pose["g_yaw"]
            else:
                target_g_yaw = new_g_yaw
        else:
            target_g_pitch = new_g_pitch
            target_g_roll = new_g_roll
            target_g_yaw = new_g_yaw
        
        self._gimbal_target.update(
            g_pitch=target_g_pitch,
            g_roll=target_g_roll,
            g_yaw=target_g_yaw
        )

    def _set_pose_target(self, new_pitch: Optional[float], new_roll: Optional[float], new_yaw: Optional[float]):
        current_pose = self.get_state("attitude")
        if any([new_pitch, new_roll, new_yaw]):
            if new_pitch == None:
                target_pitch = current_pose["pitch"]
            else:
                target_pitch = new_pitch
            if new_roll == None:
                target_roll = current_pose["roll"]
            else:
                target_roll = new_roll
            if new_yaw == None:
                target_yaw = current_pose["yaw"]
            else:
                target_yaw = new_yaw
        else:
            target_pitch = new_pitch
            target_roll = new_roll
            target_yaw = new_yaw

        self._pose_target.update(
            pitch=target_pitch,
            roll=target_roll,
            yaw=target_yaw
        )

    def _set_position_target(self, pos_x: Optional[float], pos_y: Optional[float], pos_z: Optional[float]):
        self._position_flag = False
        self._position_target.update(
            lat=pos_x,
            lon=pos_y,
            alt=pos_z
        )

    def _set_velocity_target(self, vel_x: Optional[float], vel_y: Optional[float], vel_z: Optional[float]):
        if vel_x != None:
            x = max(min(vel_x, MAX_SPEED), -MAX_SPEED)
        else:
            x = None
        if vel_y != None:
            y = max(min(vel_y, MAX_SPEED), -MAX_SPEED)
        else:
            y = None
        if vel_z != None:
            z = max(min(vel_z, MAX_CLIMB), -MAX_CLIMB)
        else:
            z = None

        self._velocity_target.update(
            speedX=x,
            speedY=y,
            speedZ=z
        )

    def _update_kinematics(self):
        self.t_current = time.time()
        dt = self.t_current - self.t_last
        self._update_velocity(dt)
        self._update_position(dt)
        self._update_drone_pose(dt)
        self._update_gimbal_pose(dt)
        self._update_battery(dt)

    def _update_position(self, dt):
        prev_position = self.get_current_position()
        vel = self.get_state("velocity")

        if prev_position == None or vel == None:
            logger.error("_update_position: Failed to retrieve current position and velocity...")
            logger.error(f"Current position: {prev_position}")
            logger.error(f"Velocity: {vel}")
            return
        if (prev_position[0] == None
            or prev_position[1] == None
            or prev_position[2] == None):
            logger.error("_update_position: Current position improperly set...")
            logger.error(f"Previous lat: {prev_position[0]}")
            logger.error(f"Previous lon: {prev_position[1]}")
            logger.error(f"Previous alt: {prev_position[2]}")
            return
        
        new_pos = self.get_new_latlon(prev_position[0], prev_position[1], dt * vel["speedX"], dt * vel["speedY"])
        self.set_current_position(
            new_pos[0],
            new_pos[1],
            prev_position[2] + (dt * vel["speedZ"])
        )

    def _update_velocity(self, dt):
        dv = self.get_state("acceleration")
        prev_vel = self.get_state("velocity")

        if dv == None or prev_vel == None:
            logger.error("_update_velocity: Failed to retrieve previous velocity and acceleration...")
            logger.error(f"Previous velocity: {prev_vel}")
            logger.error(f"Previous acceleration: {dv}")
            return
        if (prev_vel["speedX"] == None
            or prev_vel["speedY"] == None
            or prev_vel["speedZ"] == None):
            logger.error("_update_velocity: Component of previous velocity improperly set...")
            logger.error(f"Previous speedX: {prev_vel["speedX"]}")
            logger.error(f"Previous speedY: {prev_vel["speedY"]}")
            logger.error(f"Previous speedZ: {prev_vel["speedZ"]}")
            return
        if (dv["accX"] == None
            or dv["accY"] == None
            or dv["accZ"] == None):
            logger.error("_update_velocity: Component of acceleration improperly set...")
            logger.error(f"accX: {dv["accX"]}")
            logger.error(f"accY: {dv["accY"]}")
            logger.error(f"accZ: {dv["accZ"]}")
            return

        self.set_velocity(
            prev_vel["speedX"] + (dt * dv["accX"]),
            prev_vel["speedY"] + (dt * dv["accY"]),
            prev_vel["speedZ"] + (dt * dv["accZ"])
        )

    def _update_drone_pose(self, dt):
        dp = self.get_state("drone_rotation")
        prev_pose = self.get_state("attitude")

        if dp == None or prev_pose == None:
            logger.error("_update_drone_pose: Failed to retrieve prior drone pose and and rotation rates...")
            logger.error(f"Previous pose: {prev_pose}")
            logger.error(f"Rotation rates: {dp}")
            return
        if (prev_pose["pitch"] == None
        or prev_pose["roll"] == None
        or prev_pose["yaw"] == None):
            logger.error("update_drone_pose: Component of previous pose improperly set...")
            logger.error(f"Pitch: {prev_pose["pitch"]}")
            logger.error(f"Roll: {prev_pose["roll"]}")
            logger.error(f"Yaw: {prev_pose["yaw"]}")
            return
        if (dp["pitch_rate"] == None
            or dp["roll_rate"] == None
            or dp["yaw_rate"] == None):
            logger.error("update_drone_pose: Component of pose rotation rate improperly set...")
            logger.error(f"Pitch rate: {dp["pitch_rate"]}")
            logger.error(f"Roll rate: {dp["roll_rate"]}")
            logger.error(f"Yaw rate: {dp["yaw_rate"]}")
            return
        if (self._pose_target["pitch"] == None
            or self._pose_target["roll"] == None
            or self._pose_target["yaw"] == None):
            logger.error("_update_drone_pose: Component of drone pose target improperly set...")
            logger.error(f"Pitch target: {self._pose_target["pitch"]}")
            logger.error(f"Roll target: {self._pose_target["roll"]}")
            logger.error(f"Yaw target: {self._pose_target["yaw"]}")
            return

        update_rate_flag = False

        # Check for overshoot and constrain to pose target for each characteristic
        if abs(self._pose_target["pitch"] - prev_pose["pitch"]) <= dt * dp["pitch_rate"]:
            pitch = self._pose_target["pitch"]
            dp["pitch_rate"] = 0
            update_rate_flag = True
        else:
            pitch = (prev_pose["pitch"] + (dt * dp["pitch_rate"])) % 360
        if abs(self._pose_target["roll"] - prev_pose["roll"]) <= dt * dp["roll_rate"]:
            roll = self._pose_target["roll"]
            dp["roll_rate"] = 0
            update_rate_flag = True
        else:
            roll = (prev_pose["roll"] + (dt * dp["roll_rate"])) % 360
        if abs(self._pose_target["yaw"] - prev_pose["yaw"]) <= dt * dp["yaw_rate"]:
            yaw = self._pose_target["yaw"]
            dp["yaw_rate"] = 0
            update_rate_flag = True
        else:
            yaw = (prev_pose["yaw"] + (dt * dp["yaw_rate"])) % 360
        
        self.set_attitude(pitch, roll, yaw)

        if update_rate_flag:
            self._set_drone_rotation(dp["pitch_rate"], dp["roll_rate"], dp["yaw_rate"])

    def _update_gimbal_pose(self, dt):
        dp = self.get_state("gimbal_rotation")
        prev_pose = self.get_state("gimbal_pose")

        if dp == None or prev_pose == None:
            logger.error("_update_gimbal_pose: Failed to retrieve previous gimbal pose and rotation rates...")
            logger.error(f"Previous gimbal pose: {prev_pose}")
            logger.error(f"Gimbal rotation rates: {dp}")
            return
        if (prev_pose["g_pitch"] == None
            or prev_pose["g_roll"] == None
            or prev_pose["g_yaw"] == None):
            logger.error("_update_gimbal_pose: Component of previous gimbal pose improperly set...")
            logger.error(f"Gimbal pitch: {prev_pose["g_pitch"]}")
            logger.error(f"Gimbal roll: {prev_pose["g_roll"]}")
            logger.error(f"Gimbal yaw: {prev_pose["g_yaw"]}")
            return
        if (dp["g_pitch_rate"] == None
            or dp["g_roll_rate"] == None
            or dp["g_yaw_rate"] == None):
            logger.error("_update_gimbal_pose: Component of gimbal rotation rate improperly set...")
            logger.error(f"Gimbal pitch rate: {dp["g_pitch_rate"]}")
            logger.error(f"Gimbal roll rate: {dp["g_roll_rate"]}")
            logger.error(f"Gimbal yaw rate: {dp["g_yaw_rate"]}")
            return
        if (self._gimbal_target["g_pitch"] == None
            or self._gimbal_target["g_roll"] == None
            or self._gimbal_target["g_yaw"] == None):
            logger.error("_update_gimbal_pose: Component of gimbal target improperly set...")
            logger.error(f"Gimbal target pitch: {self._gimbal_target["g_pitch"]}")
            logger.error(f"Gimbal target roll: {self._gimbal_target["g_roll"]}")
            logger.error(f"Gimbal target yaw: {self._gimbal_target["g_yaw"]}")
            return

        update_rate_flag = False
        # Check for overshoot and constrain to gimbal target for each characteristic
        if abs(self._gimbal_target["g_pitch"] - prev_pose["g_pitch"]) <= dt * dp["g_pitch_rate"]:
            g_pitch = self._gimbal_target["g_pitch"]
            dp["g_pitch_rate"] = 0
            update_rate_flag = True
        else:
            g_pitch = (prev_pose["g_pitch"] + (dt * dp["g_pitch_rate"])) % 360
        if abs(self._gimbal_target["g_roll"] - prev_pose["g_roll"]) <= dt * dp["g_roll_rate"]:
            g_roll = self._gimbal_target["g_roll"]
            dp["g_roll_rate"] = 0
            update_rate_flag = True
        else:
            g_roll = (prev_pose["g_roll"] + (dt * dp["g_roll_rate"])) % 360
        if abs(self._gimbal_target["g_yaw"] - prev_pose["g_yaw"]) <= dt * dp["g_yaw_rate"]:
            g_yaw = self._gimbal_target["g_yaw"]
            dp["g_yaw_rate"] = 0
            update_rate_flag = True    
        else:
            g_yaw = (prev_pose["g_yaw"] + (dt * dp["g_yaw_rate"])) % 360

        self.set_gimbal_pose(g_pitch, g_roll, g_yaw)

        if update_rate_flag:
            self._set_gimbal_rotation(dp["g_pitch_rate"], dp["g_roll_rate"], dp["g_yaw_rate"])

    def _update_battery(self, dt):
        current_charge = self.get_state("battery_percent")
        current_state = self.get_state("flight_state")
        if current_state == common_protocol.FlightStatus.LANDED or current_state == common_protocol.FlightStatus.IDLE:
            new_charge = current_charge - dt * LANDED_DRAIN_RATE
        else:
            new_charge = current_charge - dt * ACTIVE_DRAIN_RATE
        self.set_battery_percent(new_charge)

    def _zero_velocity(self):
        self._set_velocity_target(0, 0, 0)
        self._set_position_target(None, None, None)
        current_velocity = self.get_state("velocity")
        
        if current_velocity == None:
            logger.error("_zero_velocity: Failed to retrieve current velocity...")
            logger.error(f"Current stored velocity: {current_velocity}")
            return
        if (current_velocity["speedX"] == None
            or current_velocity["speedY"] == None
            or current_velocity["speedZ"] == None):
            logger.error("_zero_velocity: Component of velocity improperly set...")
            logger.error(f"Velocity speedX: {current_velocity["speedX"]}")
            logger.error(f"Velocity speedY: {current_velocity["speedY"]}")
            logger.error(f"Velocity speedZ: {current_velocity["speedZ"]}")
            return

        acc_x = self._calculate_deceleration(current_velocity["speedX"], 0)
        acc_y = self._calculate_deceleration(current_velocity["speedY"], 0)
        acc_z = self._calculate_deceleration(current_velocity["speedZ"], 0)
        self._set_acceleration(acc_x, acc_y, acc_z)

    def get_new_latlon(self, ref_lat: float, ref_lon: float, dist_x: float, dist_y: float) -> tuple[float, float]:
        new_lat = ref_lat + (dist_x / M_PER_LAT_DEG)
        m_per_deg_lon = np.cos(np.deg2rad(new_lat)) * M_PER_LAT_DEG
        new_lon = ref_lon + (dist_y / m_per_deg_lon)
        return (new_lat, new_lon)