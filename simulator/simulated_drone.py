import asyncio
import logging
import time
import numpy as np

import protocol.common_pb2 as common_protocol

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
        self._position_target = None
        self._pose_target = None
        self._gimbal_target = None
        self._velocity_target = None

        self.set_current_position(lat, lon, alt)


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
        self._zeroize_velocity()
        if self.get_current_position()[2] > 0:
            self.set_flight_state(common_protocol.HOVERING)
        else:
            self.set_flight_state(common_protocol.IDLE)
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
        self._position_target = (current_position[0], current_position[1], 0)
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
    
    def get_current_position(self):
        try:
            return (
                self.current_position["lat"],
                self.current_position["lon"],
                self.current_position["alt"]
            )
        except:
            logger.error("Unable to retrieve current position")
            return None

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

    def set_current_position(self, lat: float, lon: float, alt: float):
        self.current_position = {
            "lat": lat,
            "lon": lon,
            "alt": alt
        }

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
        if self._position_target[0] - current_position[0] > 0:
            acc_x = MAX_ACCELERATION
        else:
            acc_x = -MAX_ACCELERATION
        if self._position_target[1] - current_position[1] > 0:
            acc_y = MAX_ACCELERATION
        else:
            acc_y = -MAX_ACCELERATION
        if self._position_target[2] - current_position[2] > 0:
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
        acceleration = self.get_state["acceleration"]
        velocity = self.get_state["velocity"]
        current_position = self.get_current_position()
        dist_x = self._position_target[0] - current_position[0]
        dist_y = self._position_target[1] - current_position[1]
        dist_z = self._position_target[2] - current_position[2]
        if abs(dist_x) <= LATERAL_BRAKE_THRESHOLD:
            acceleration["accX"] = self._calculate_deceleration(velocity["speedX"], dist_x)
        if abs(dist_y) <= LATERAL_BRAKE_THRESHOLD:
            acceleration["accY"] = self._calculate_deceleration(velocity["speedY"], dist_y)
        if abs(dist_z) <= VERTICAL_BRAKE_THRESHOLD:
            acceleration["accZ"] = self._calculate_deceleration(velocity["speedZ"], dist_z)
        self._set_acceleration(acceleration["accX"], acceleration["accY"], acceleration["accZ"])

    def _check_drone_pose_reached(self):
        pose = self.get_state("attitude")
        if (abs(self._pose_target[0] - pose[0]) <= MATCH_TOLERANCE
            and abs(self._pose_target[1] - pose[1]) <= MATCH_TOLERANCE
            and abs(self._pose_target[2] - pose[2]) <= MATCH_TOLERANCE):
            self._set_drone_rotation(0, 0, 0)
            self._pose_target = None

    def _check_gimbal_pose_reached(self):
        g_pose = self.get_state("gimbal_pose")
        if (abs(self._gimbal_target[0] - g_pose["g_pitch"]) <= MATCH_TOLERANCE
            and abs(self._gimbal_target[1] - g_pose["g_roll"]) <= MATCH_TOLERANCE
            and abs(self._gimbal_target[2] - g_pose["g_yaw"]) <= MATCH_TOLERANCE):
            self._set_gimbal_rotation(0, 0, 0)
            self._gimbal_target = None

    def _check_velocity_reached(self):
        velocity = self.get_state["velocity"]
        acceleration = self.get_state["acceleration"]
        vel_x = velocity["speedX"]
        vel_y = velocity["speedY"]
        vel_z = velocity["speedZ"]
        if abs(vel_x - self._velocity_target["speedX"]) <= MATCH_TOLERANCE or abs(vel_x) >= MAX_SPEED:
            acceleration["accX"] = 0
        if abs(vel_y - self._velocity_target["speedY"]) <= MATCH_TOLERANCE or abs(vel_y) >= MAX_SPEED:
            acceleration["accY"] = 0
        if abs(vel_z - self._velocity_target["speedZ"]) <= MATCH_TOLERANCE or abs(vel_z) >= MAX_CLIMB:
            acceleration["accZ"] = 0
        # If all velocity targets are achieved, delete the current velocity target
        if acceleration["accX"] == 0 and acceleration["accY"] == 0 and acceleration["accZ"] == 0:
            self._velocity_target = None
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
        new_pos = get_new_latlon(prev_position[0], prev_position[1], dt * vel["speedX"], dt * vel["speedY"])
        self.set_current_position(
            new_pos[0],
            new_pos[1],
            prev_position[2] + (dt * vel["speedZ"])
        )

    def _update_velocity(self, dt):
        dv = self.get_state("acceleration")
        prev_vel = self.get_state("velocity")
        self.set_velocity(
            prev_vel["speedX"] + (dt * dv["accX"]),
            prev_vel["speedY"] + (dt * dv["accY"]),
            prev_vel["speedZ"] + (dt * dv["accZ"])
        )

    def _update_drone_pose(self, dt):
        dp = self.get_state("drone_rotation")
        prev_pose = self.get_state("attitude")
        # Check for overshoot and constrain to pose target for each characteristic
        if abs(self._pose_target[0] - prev_pose["pitch"]) <= dt * dp["pitch_rate"]:
            pitch = self._pose_target[0]
        else:
            pitch = (prev_pose["pitch"] + (dt * dp["pitch_rate"])) % 360
        if abs(self._pose_target[1] - prev_pose["roll"]) <= dt * dp["roll_rate"]:
            roll = self._pose_target[1]
        else:
            roll = (prev_pose["roll"] + (dt * dp["roll_rate"])) % 360
        if abs(self._pose_target[2] - prev_pose["yaw"]) <= dt * dp["yaw_rate"]:
            yaw = self._pose_target[2]
        else:
            yaw = (prev_pose["yaw"] + (dt * dp["yaw_rate"])) % 360
        
        self.set_attitude(pitch, roll, yaw)

    def _update_gimbal_pose(self, dt):
        dp = self.get_state("gimbal_rotation")
        prev_pose = self.get_state("gimbal_pose")

        # Check for overshoot and constrain to gimbal target for each characteristic
        if abs(self._gimbal_target[0] - prev_pose["g_pitch"]) <= dt * dp["g_pitch_rate"]:
            g_pitch = self._gimbal_target[0]
        else:
            g_pitch = (prev_pose["g_pitch"] + (dt * dp["g_pitch_rate"])) % 360
        if abs(self._gimbal_target[1] - prev_pose["g_roll"]) <= dt * dp["g_roll_rate"]:
            g_roll = self._gimbal_target[1]
        else:
            g_roll = (prev_pose["g_roll"] + (dt * dp["g_roll_rate"])) % 360
        if abs(self._gimbal_target[2] - prev_pose["g_yaw"]) <= dt * dp["g_yaw_rate"]:
            g_yaw = self._gimbal_target[2]
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

def get_new_latlon(ref_lat: float, ref_lon: float, dist_x: float, dist_y: float) -> tuple[float, float]:
    new_lat = ref_lat + (dist_x / M_PER_LAT_DEG)
    m_per_deg_lon = np.cos(np.deg2rad(new_lat)) * M_PER_LAT_DEG
    new_lon = ref_lon + (dist_y / m_per_deg_lon)
    return (new_lat, new_lon)