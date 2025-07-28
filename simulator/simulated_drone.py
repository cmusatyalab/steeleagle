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
TICK_COUNT = 60
TICK_RATE = 1 / TICK_COUNT
DEFAULT_LAT = 40.41368353053923
DEFAULT_LON = -79.9489233699767
DEFAULT_ALT = 0

class SimulatedDrone():
    def __init__(self, ip, lat=DEFAULT_LAT, lon=DEFAULT_LON, alt=DEFAULT_ALT):
        self._device_type = "Digital Drone"
        self.connection_ip = ip
        self._active_connection = False
        self._current_flight_state = "landed"
        self._state = {}
        self._initialize_internal_dicts()
        self.set_current_position(lat, lon, alt)

    def _initialize_internal_dicts(self):
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


    async def state_loop(self):
        while self._active_connection:
            if self._pending_action:
                if self._active_action:
                    self._cancel_current_action()
                while self._pending_action:
                    await asyncio.sleep(1)
                self._calculate_acceleration_direction()
            if self._velocity_target:
                self._check_velocity_reached()
            if self._position_target:
                self._check_braking_thresholds()
            if self._pose_target:
                self._check_drone_pose_reached()
            if self._gimbal_target:
                self._check_gimbal_pose_reached()
            self._update_kinematics()
            time_elapsed = self.t_current - self.t_last
            self.t_last = self.t_current
            await asyncio.sleep(TICK_RATE - time_elapsed)
        logger.info("Connection terminated, shutting down...")

    def _cancel_current_action(self):
        # get to 0, 0, 0 velocity, then cancel
        # clear existing targets
        self._zero_velocity()
        if self.get_current_position()[2] is not None and self.get_current_position()[2] > 0: # type: ignore
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
        else:
            self.set_flight_state(common_protocol.FlightStatus.IDLE)
        self._active_action = None

    """ Connectivity Methods """

    def connect(self) -> bool:
        if self._active_connection == False:
            self._active_connection = True
            logger.info("Connection established with simulated digital drone...")
            logger.info("Starting internal state loop...")
            asyncio.run(self.state_loop())
            logger.info("Internal state loop active...")
            return True
        logger.warning("Attempted multiple connections on simulated drone object.")
        return False

    def connection_state(self) -> bool:
        return self._active_connection
    
    def disconnect(self) -> bool:
        if self._active_connection:
            self._active_connection = False
            logger.info("Disconnected from simulated digital drone...")
            return True
        logger.warning("Attempted to disconnect without active connection to simulated drone")
        return False
    
    """ Operational Methods """

    def take_off(self):
        pass

    def land(self):
        current_position = self.get_current_position()
        # NOTE: Assumes ground plane is flat and at value 0
        #self._position_target = (current_position[0], current_position[1], 0)
        # set position target on ground
        # change mode to landing/moving
        # set acceleration values
        # wait for completion
        # report completion
        pass

    def move_to(self, lat, lon, altitude, heading_mode, bearing):
        # check heading mode
            # set attitude target for drone pose if necessary
        # set position target
        # set velocity target to max by default
        # change mode to flying/moving
        # wait for completion
        # report completion
        pass

    def extended_move_to(self, lat, lon, altitude, heading_mode, bearing, lateral_vel, up_vel, angular_vel):
        # check heading mode
            # set attitude target for drone pose if necessary
        # set position target
        # set velocity target to specified velocities
            # may need to normalize against the lateral velocity
        # change mode to flying/moving
        # wait for completion
        # report completion
        pass

    def set_target(self, gimbal_id, control_mode, pitch, roll, yaw):
        # based on angular velocity?
        pass

    def set_home_location(self, lat, lon, alt):
        self.home_location = {
            "lat": lat,
            "lon": lon,
            "alt": alt
        }
        logger.info(f"Home location updated to ({lon}, {lat}) at elevation {alt}")

    def _update_state(self, characteristic: str, value):
        if characteristic not in self._state:
            logger.info(f"Adding {characteristic} to internal state")
        self._state[characteristic] = value

    """ ACK methods """

    def check_flight_state(self, target_state: str):
        if target_state == self._current_flight_state:
            return True
        return False
    
    def get_current_position(self) -> list[Optional[float]]:
        try:
            return [
                self.current_position["lat"],
                self.current_position["lon"],
                self.current_position["alt"]
            ]
        except:
            logger.error("Unable to retrieve current position")
            return [None, None, None]

    def get_home_location(self):
        try:
            return (
                self.home_location["lat"],
                self.home_location["lon"],
                self.home_location["alt"]
            )
        except:
            logger.error("Home location not set")
            return None
        
    def get_state(self, characteristic: str):
        if characteristic not in self._state:
            logger.error(f"{characteristic} not included in drone state. Unable to retrieve")
            return None
        return self._state[characteristic]
        
    """ Internal State Methods """

    def set_attitude(self, pitch: float, roll: float, yaw: float):
        attitude = {
            "pitch": pitch,
            "roll": roll,
            "yaw": yaw
        }
        self._update_state("attitude", attitude)
    
    def set_battery_percent(self, starting_charge: float):
        self._update_state("battery_percent", starting_charge)

    def set_current_position(self, new_lat: float, new_lon: float, new_alt: float):
        self.current_position.update(
            lat=new_lat,
            lon=new_lon,
            alt=new_alt
        )

    def set_flight_state(self, flight_state: common_protocol.FlightStatus):
        self._update_state("flight_state", flight_state)

    def set_gimbal_pose(self, pitch: float, roll: float, yaw: float):
        gimbal_pose = {
            "g_pitch": pitch,
            "g_roll": roll,
            "g_yaw": yaw
        }
        self._update_state("gimbal_pose", gimbal_pose)

    def set_magnetometer(self, condition_code: int):
        # 0 for good, 1 for calibration, 2 for perturbation
        self._update_state("magnetometer", condition_code)

    def set_name(self, drone_id: str):
        self._update_state("drone_id", drone_id)

    def set_velocity(self, vel_x: float, vel_y: float, vel_z: float):
        velocity = {
            "speedX": max(min(vel_x, MAX_SPEED), -MAX_SPEED),
            "speedY": max(min(vel_y, MAX_SPEED), -MAX_SPEED),
            "speedZ": max(min(vel_z, MAX_CLIMB), -MAX_CLIMB)
        }
        self._update_state("velocity", velocity)
    
    def set_satellites(self, satellite_count: int):
        self._update_state("satellite_count", satellite_count)
    
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

    def _calculate_deceleration(self, vel_val: float, dist_remaining: float):
        if vel_val < 0:
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
            return
        if (self._gimbal_target["g_pitch"] == None
            or self._gimbal_target["g_roll"] == None
            or self._gimbal_target["g_yaw"] == None):
            logger.error("Gimbal pose target not properly set...")
            logger.error(f"Gimbal pitch: {self._gimbal_target["g_pitch"]}")
            logger.error(f"Gimbal roll: {self._gimbal_target["g_roll"]}")
            logger.error(f"Gimbal yaw: {self._gimbal_target["g_yaw"]}")
            return
        
        if (abs(self._gimbal_target["g_pitch"] - g_pose["g_pitch"]) <= MATCH_TOLERANCE
            and abs(self._gimbal_target["g_roll"] - g_pose["g_roll"]) <= MATCH_TOLERANCE
            and abs(self._gimbal_target["g_yaw"] - g_pose["g_yaw"]) <= MATCH_TOLERANCE):
            self._set_gimbal_rotation(0, 0, 0)
            self._gimbal_target.update(
                g_pitch=None,
                g_roll=None,
                g_yaw=None
            )

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

        if abs(vel_x - self._velocity_target["speedX"]) <= MATCH_TOLERANCE or abs(vel_x) >= MAX_SPEED:
            acceleration["accX"] = 0
        if abs(vel_y - self._velocity_target["speedY"]) <= MATCH_TOLERANCE or abs(vel_y) >= MAX_SPEED:
            acceleration["accY"] = 0
        if abs(vel_z - self._velocity_target["speedZ"]) <= MATCH_TOLERANCE or abs(vel_z) >= MAX_CLIMB:
            acceleration["accZ"] = 0
        # If all velocity targets are achieved, delete the current velocity target
        if acceleration["accX"] == 0 and acceleration["accY"] == 0 and acceleration["accZ"] == 0:
            self._velocity_target.update(
                speedX=None,
                speedY=None,
                speedZ=None
            )
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
        
        new_pos = get_new_latlon(prev_position[0], prev_position[1], dt * vel["speedX"], dt * vel["speedY"])
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

        # Check for overshoot and constrain to pose target for each characteristic
        if abs(self._pose_target["pitch"] - prev_pose["pitch"]) <= dt * dp["pitch_rate"]:
            pitch = self._pose_target["pitch"]
        else:
            pitch = (prev_pose["pitch"] + (dt * dp["pitch_rate"])) % 360
        if abs(self._pose_target["roll"] - prev_pose["roll"]) <= dt * dp["roll_rate"]:
            roll = self._pose_target["roll"]
        else:
            roll = (prev_pose["roll"] + (dt * dp["roll_rate"])) % 360
        if abs(self._pose_target["yaw"] - prev_pose["yaw"]) <= dt * dp["yaw_rate"]:
            yaw = self._pose_target["yaw"]
        else:
            yaw = (prev_pose["yaw"] + (dt * dp["yaw_rate"])) % 360
        
        self.set_attitude(pitch, roll, yaw)

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

        # Check for overshoot and constrain to gimbal target for each characteristic
        if abs(self._gimbal_target["g_pitch"] - prev_pose["g_pitch"]) <= dt * dp["g_pitch_rate"]:
            g_pitch = self._gimbal_target["g_pitch"]
        else:
            g_pitch = (prev_pose["g_pitch"] + (dt * dp["g_pitch_rate"])) % 360
        if abs(self._gimbal_target["g_roll"] - prev_pose["g_roll"]) <= dt * dp["g_roll_rate"]:
            g_roll = self._gimbal_target["g_roll"]
        else:
            g_roll = (prev_pose["g_roll"] + (dt * dp["g_roll_rate"])) % 360
        if abs(self._gimbal_target["g_yaw"] - prev_pose["g_yaw"]) <= dt * dp["g_yaw_rate"]:
            g_yaw = self._gimbal_target["g_yaw"]
        else:
            g_yaw = (prev_pose["g_yaw"] + (dt * dp["g_yaw_rate"])) % 360

        self.set_gimbal_pose(g_pitch, g_roll, g_yaw)

    def _update_battery(self, dt):
        current_charge = self.get_state("battery_percent")
        if self._current_flight_state == "landed":
            new_charge = current_charge - dt * LANDED_DRAIN_RATE
        else:
            new_charge = current_charge - dt * ACTIVE_DRAIN_RATE
        self.set_battery_percent(new_charge)

    def _zero_velocity(self):
        pass

def get_new_latlon(ref_lat: float, ref_lon: float, dist_x: float, dist_y: float) -> tuple[float, float]:
    new_lat = ref_lat + (dist_x / M_PER_LAT_DEG)
    m_per_deg_lon = np.cos(np.deg2rad(new_lat)) * M_PER_LAT_DEG
    new_lon = ref_lon + (dist_y / m_per_deg_lon)
    return (new_lat, new_lon)