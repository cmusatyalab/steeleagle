import asyncio
import logging
import time

import common_pb2 as common_protocol
import numpy as np

logger = logging.getLogger(__name__)
M_PER_LAT_DEG = 111139
LANDED_DRAIN_RATE = 0.03
ACTIVE_DRAIN_RATE = 0.06
MAX_SPEED = 15  # m/s
MAX_CLIMB = 4  # m/s
MAX_ACCELERATION = 10  # m/s^2
MAX_ROTA_RATE = 250
MAX_YAW_RATE = 180
MAX_G_ROTA_RATE = 300
LATERAL_BRAKE_THRESHOLD = MAX_SPEED * 1.5
VERTICAL_BRAKE_THRESHOLD = MAX_CLIMB * 1.5
MATCH_TOLERANCE = 0.1
POSE_TOLERANCE = 0.1
DEG_MATCH_TOLERANCE = 0.00003  # ~3m error in degrees of lat
ALT_MATCH_TOLERANCE = 0.1  # m
TICK_COUNT = 60
TICK_RATE = 1 / TICK_COUNT
BREAKING_BUFFER = TICK_RATE * MAX_SPEED * 10
DEFAULT_LAT = 40.41368353053923
DEFAULT_LON = -79.9489233699767
DEFAULT_ALT = 0
DEFAULT_SAT_COUNT = 16
TASK_TIMEOUT = 10  # value in seconds
MOVE_TIMEOUT = 120
EARTH_RADIUS_M = 6371000


class SimulatedDrone:
    def __init__(
        self,
        ip,
        drone_id="Simulated Drone",
        lat=DEFAULT_LAT,
        lon=DEFAULT_LON,
        alt=DEFAULT_ALT,
        takeoff_alt=10,
        mag_interference=0,
    ):
        self.init_complete_flag = False
        self._device_type = "Digital Drone"
        self.connection_ip = ip
        self._active_connection = False
        self._takeoff_alt = takeoff_alt
        self._state = {}
        self.set_name(drone_id)
        self._initialize_internal_dicts()
        self.set_current_position(lat, lon, alt)
        self.set_home_location(lat, lon, alt)
        self.set_magnetometer(mag_interference)
        self.init_complete_flag = True

    def _initialize_internal_dicts(self) -> None:
        self.current_position: dict[str, float | None] = {
            "lat": None,
            "lon": None,
            "alt": None,
        }
        self._position_target: dict[str, float | None] = {
            "lat": None,
            "lon": None,
            "alt": None,
        }
        self._pose_target: dict[str, float | None] = {
            "pitch": None,
            "roll": None,
            "yaw": None,
        }
        self._gimbal_target: dict[str, float | None] = {
            "g_pitch": None,
            "g_roll": None,
            "g_yaw": None,
        }
        self._velocity_target: dict[str, float | None] = {
            "speedX": None,
            "speedY": None,
            "speedZ": None,
        }
        self._pending_action = False
        self._active_action = False
        self._position_flag = False
        self.set_velocity(0, 0, 0)
        self.set_angular_velocity(0)
        self.set_gimbal_pose(0, 0, 0)
        self.set_attitude(0, 0, 0)
        self._set_acceleration(0, 0, 0)
        self._set_drone_rotation(0, 0, 0)
        self._set_gimbal_rotation(0, 0, 0)
        self.set_battery_percent(100)
        self.set_satellites(DEFAULT_SAT_COUNT)
        self.set_flight_state(common_protocol.FlightStatus.LANDED)

    """ Task & State Management """

    async def state_loop(self):
        """
        Primary event loop for the digital drone, initiated through the connect() command.
        Each iteration of the loop checks for active aspect targets and executes updates to
        contributing kinematic properties as needed. After target checks, the update_kinematics()
        call is responsible for updating the values representing the simulated drone in the modeled
        space. The rate of execution of the event loop is mainly controlled through the TICK_RATE
        constant.
        """
        self.t_baseline = time.time()
        while self._active_connection:
            self.t_cycle_start = time.time()
            logger.debug(
                f"-----Current Time: {self.t_cycle_start - self.t_baseline} -----"
            )
            # Set via register_pending_task(), preempts currently executing task if one exists
            if self._pending_action:
                if self._active_action:
                    self._cancel_current_action()
                else:
                    self._pending_action = False
                    logger.debug(
                        f"state_loop: Pending action changed to: {self._pending_action}"
                    )
            # Used to set the appropriate sign for acceleration values
            if self._check_target_active("position"):
                self._calculate_acceleration_direction()
            # Limits velocity if a target is provided (i.e. via extended_move_to)
            if self._check_target_active("velocity"):
                self._check_velocity_reached()
                logger.debug(f"state_loop: Velocity Target: {self._velocity_target}")
            # Modifies previously calculated acceleration values to prevent overshoot
            if self._check_target_active("position"):
                self._check_braking_thresholds()
                logger.debug(f"state_loop: Position Target: {self._position_target}")
            # Prevent overshoot of drone and gimbal pose components while rotating
            if self._check_target_active("pose"):
                self._check_drone_pose_reached()
            if self._check_target_active("gimbal"):
                self._check_gimbal_pose_reached()
            self._update_kinematics()
            self.t_cycle_finish = time.time()
            time_elapsed = self.t_cycle_finish - self.t_cycle_start
            self.t_last = self.t_current
            await asyncio.sleep(TICK_RATE - time_elapsed)
        logger.info("Connection terminated, shutting down...")

    async def _wait_for_condition(self, condition_fn, timeout=None, interval=0.1):
        """
        Allows for graceful wait/timeout following initiation of an async procedure.
        Higher interval values run the risk of allowing kinematic value overshoots.
        """
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

    async def _cancel_current_action(self):
        """
        Blocking call that stops the drone and clears any targets set as part of the previous command.
        Places the drone in a hover state if airborne (elevation > 0) or an idle state if on the ground.
        Clearing the active_action flag allows pending action registration to proceed.
        """
        logger.warning("Canceling active action...")
        self._zero_velocity()
        stop_result = await self._wait_for_condition(
            lambda: self.is_stopped(), timeout=TASK_TIMEOUT, interval=0.1
        )
        if not stop_result:
            logger.error(
                "cancel_current_action: Failed to zero velocity prior to cancellation..."
            )
        else:
            logger.info(
                f"{self.get_state('drone_id')} successfully stopped prior to canceling current action..."
            )
        if self._check_target_active("gimbal"):
            self._set_gimbal_rotation(0, 0, 0)
            self._set_gimbal_target(None, None, None)
        if self._check_target_active("pose"):
            self._set_drone_rotation(0, 0, 0)
            self._set_pose_target(None, None, None)

        if (
            self.get_current_position()[2] is not None
            and self.get_current_position()[2] > 0
        ):
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
        else:
            self.set_flight_state(common_protocol.FlightStatus.IDLE)
        self._active_action = False

    async def _register_pending_task(self):
        """
        Attempts to signal to the event loop that a new task is being initiated. Fails if there is already
        a pending task in the process of registration. Otherwise, waits until the task lock controlled by the
        active_action flag is released by the cancel_current_action() call in the state loop.
        """
        if self._pending_action:
            return False
        self._pending_action = True
        logger.debug(
            f"register_pending_task: Pending action set to {self._pending_action}"
        )
        # Allow state loop time to process flags even if no active task currently exists
        await asyncio.sleep(1)
        result = await self._wait_for_condition(
            lambda: self.is_task_lock_open(), timeout=TASK_TIMEOUT, interval=0.1
        )
        if result:
            self._active_action = True
        return result

    """ Connection Methods """

    async def connect(self) -> bool:
        """
        Called externally by the controlling entity to activate the state loop and start the drone's
        internal clock. Presumes the controlling entity has a direct handle to the digital drone
        object and does not currently simulate message passing between drone and interface driver.
        """
        if not self._active_connection:
            self._active_connection = True
            logger.info("Connection established with simulated digital drone...")
            logger.info("Starting internal state loop...")
            self.t_current = time.time()
            self.t_last = self.t_current
            self._loop = asyncio.create_task(self.state_loop())
            logger.info("Internal state loop active...")
            return True
        return True

    def connection_state(self) -> bool:
        return self._active_connection

    async def disconnect(self) -> bool:
        """
        Called externally by the controlling entity to simulate shutting the drone down. Cancels the asyncio
        event loop started in the connect() call and sets the connection flag off to trigger graceful exit
        of the drone's state loop.
        """
        if self._active_connection:
            self._active_connection = False
            self._loop.cancel()
            logger.info("Disconnected from simulated digital drone...")
            return True
        logger.warning(
            "Attempted to disconnect without active connection to simulated drone..."
        )
        return False

    """ API Operational Methods """

    async def take_off(self):
        """
        Implements the kinematic component changes required to simulate the SteelEagle take_off command via
        the usage of a position target. Once set, the drone's internal state loop controls acceleration values
        to bring the drone to the takeoff elevation specified as part of the drone's init args.
        """
        logger.info("Initiating take off sequence...")
        if not self.check_flight_state(
            common_protocol.FlightStatus.LANDED
        ) and not self.check_flight_state(common_protocol.FlightStatus.IDLE):
            logger.error(
                f"take_off: {self.get_state('drone_id')} unable to execute take off command when not landed..."
            )
            logger.error(f"Current flight state: {self.get_state('flight_state')}")
            return False

        result = await self._register_pending_task()
        if not result:
            logger.warning(
                "take_off: Pending task already queued, unable to register take off command..."
            )
            return False
        else:
            logger.info(
                "take_off: Task successfully registered, beginning procedure..."
            )

        self.set_flight_state(common_protocol.FlightStatus.TAKING_OFF)
        current_position = self.get_current_position()
        self._set_position_target(
            current_position[0], current_position[1], self._takeoff_alt
        )

        result = await self._wait_for_condition(
            lambda: self.is_takeoff_complete(), timeout=TASK_TIMEOUT, interval=0.1
        )

        if result:
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
            logger.info(f"{self.get_state('drone_id')} completed takeoff...")
        else:
            self._zero_velocity()
            await self._wait_for_condition(
                lambda: self.is_stopped(), timeout=TASK_TIMEOUT, interval=0.1
            )
            self.set_flight_state(common_protocol.FlightStatus.IDLE)
            logger.warning(f"{self.get_state('drone_id')} failed to take off...")
            current_position = self.get_current_position()
            logger.warning(
                f"Stopped in position: ({current_position[0]}, {current_position[1]}, "
                f"{current_position[2]})"
            )
        self._active_action = False
        return result

    async def land(self):
        """
        Implements the kinematic component changes required to simulate the SteelEagle land command via
        the usage of a position target. Once set, the drone's internal state loop controls acceleration values
        to bring the drone to a simulated ground point (currently presumed as elevation of 0m). Ensures the drone
        is stopped prior to descending to the target position and preserves the drone pose and gimbal pose through
        the completion of the procedure.
        """
        logger.info("Initiating landing sequence...")
        if (
            self.check_flight_state(common_protocol.FlightStatus.LANDED)
            or self.check_flight_state(common_protocol.FlightStatus.LANDING)
            or self.check_flight_state(common_protocol.FlightStatus.IDLE)
        ):
            logger.warning(
                f"land: {self.get_state('drone_id')} already landed. Ignoring command..."
            )
            return True

        result = await self._register_pending_task()
        if not result:
            logger.warning(
                "land: Pending task already queued, unable to register take off command..."
            )
            return False
        else:
            logger.info("land: Task successfully registered, beginning procedure...")

        self.set_flight_state(common_protocol.FlightStatus.LANDING)
        self._zero_velocity()
        stop_result = await self._wait_for_condition(
            lambda: self.is_stopped(), timeout=TASK_TIMEOUT, interval=0.1
        )
        if not stop_result:
            logger.warning(
                "land: Failed to stop prior to beginning descent procedure..."
            )
            self._active_action = False
            return False
        else:
            logger.info(
                f"{self.get_state('drone_id')} successfully stopped prior to executing descent procedure..."
            )

        current_position = self.get_current_position()
        self._set_position_target(current_position[0], current_position[1], 0)

        result = await self._wait_for_condition(
            lambda: self.is_landed(), timeout=MOVE_TIMEOUT, interval=0.1
        )
        self._zero_velocity()
        stop_result = await self._wait_for_condition(
            lambda: self.is_stopped(), timeout=TASK_TIMEOUT, interval=0.1
        )

        if result and stop_result:
            self.set_flight_state(common_protocol.FlightStatus.LANDED)
            logger.info(f"{self.get_state('drone_id')} completed landing...")
        else:
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
            current_position = self.get_current_position()
            logger.warning(f"{self.get_state('drone_id')} failed to land...")
            logger.warning(
                f"Current position after failed attempt: ({current_position[0]}, "
                f"{current_position[1]}, {current_position[2]})"
            )
        self._active_action = False
        return result

    async def move_to(self, lat, lon, altitude, heading_mode, bearing):
        """
        Implements the kinematic component changes required to simulate the SteelEagle move_to command via
        the usage of a position target. This variant does not allow specification of a velocity target and
        will attempt to take a least time course to the target point at maximum achievable velocity while
        avoiding position target overshoot. If pose adjustments are required to meet the requested orientation,
        they are made prior to executing movement.
        """
        logger.info("Initiating move to sequence...")

        result = await self._register_pending_task()
        if not result:
            logger.warning(
                "move_to: Pending task already queued, unable to register take off command"
            )
            return False
        else:
            logger.info("move_to: Successfully registered task, beginning procedure")

        if (
            self.check_flight_state(common_protocol.FlightStatus.LANDED)
            or self.check_flight_state(common_protocol.FlightStatus.LANDING)
            or self.check_flight_state(common_protocol.FlightStatus.IDLE)
        ):
            logger.warning(
                f"move_to: {self.get_state('drone_id')} unable to execute move command"
                "from ground. Taking off first..."
            )
            result = await self.take_off()
            if not result:
                logger.error(
                    f"move_to: {self.get_state('drone_id')} unable to take off during move_to..."
                )
                return False
            logger.info("move_to: Take off completed, beginning to movement segment...")

        self._zero_velocity()
        stop_result = await self._wait_for_condition(
            lambda: self.is_stopped(), timeout=TASK_TIMEOUT, interval=0.1
        )
        if not stop_result:
            logger.warning("move_to: Failed to stop prior to orienting drone...")
            self._active_action = False
            return False
        else:
            logger.info(
                f"{self.get_state('drone_id')} successfully stopped prior to orienting drone..."
            )

        if heading_mode == common_protocol.LocationHeadingMode.TO_TARGET:
            # Orients drone to fixed target bearing
            target_bearing = bearing
        else:
            # Orients drone along the flight path heading (face 'forward')
            target_bearing = self.calculate_bearing(lat, lon)
        self._set_pose_target(None, None, target_bearing)

        self.set_flight_state(common_protocol.FlightStatus.MOVING)
        result = await self._wait_for_condition(
            lambda: self.is_drone_oriented(), timeout=TASK_TIMEOUT, interval=0.1
        )
        if not result:
            logger.warning(
                f"{self.get_state('drone_id')} failed to orient to target bearing {target_bearing} prior to executing move..."
            )
            logger.warning(
                f"Current orientation bearing {self.get_state('attitude')['yaw']}"
            )
            self._active_action = False
            return False
        else:
            logger.info(f"Completed orientation to bearing {target_bearing}")

        self._set_position_target(lat, lon, altitude)
        result = await self._wait_for_condition(
            lambda: self._check_position_reached(), timeout=None, interval=0.1
        )
        current_position = self.get_current_position()

        if result:
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
            logger.info(
                f"{self.get_state('drone_id')} completed movement to position "
                f"({current_position[0]}, {current_position[1]}, {current_position[2]})"
            )
        else:
            self._zero_velocity()
            await self._wait_for_condition(
                lambda: self.is_stopped(), timeout=TASK_TIMEOUT, interval=0.1
            )
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
            logger.warning(
                f"{self.get_state('drone_id')} failed to move to target position ({lat}, {lon}, {altitude})..."
            )
            logger.warning(
                f"Current position: ({current_position[0]}, {current_position[1]}, {current_position[2]})"
            )
        self._active_action = False
        return result

    async def extended_move_to(
        self,
        lat,
        lon,
        altitude,
        heading_mode,
        bearing,
        lateral_vel,
        up_vel,
        angular_vel,
    ):
        """
        Implements the kinematic component changes required to simulate the SteelEagle extended_move_to command via
        the usage of both position and velocity targets. The velocity target binds the maximum velocity of the drone
        during transit to the target position and is in-place until the drone has either stopped or begun decelerating
        in the x, y, and z coordinate planes. Orientation changes are made prior to beginning movement if required.
        """
        logger.info("Initiating extended move to sequence...")

        result = await self._register_pending_task()
        if not result:
            logger.warning(
                "extended_move_to: Pending task already queued, unable to register take off command..."
            )
            return False
        else:
            logger.info(
                "extended_move_to: Successfully registered task, beginning procedure..."
            )

        if (
            self.check_flight_state(common_protocol.FlightStatus.LANDED)
            or self.check_flight_state(common_protocol.FlightStatus.LANDING)
            or self.check_flight_state(common_protocol.FlightStatus.IDLE)
        ):
            logger.warning(
                f"extended_move_to: {self.get_state('drone_id')} unable to execute move command"
                "from ground. Taking off first..."
            )
            result = await self.take_off()
            if not result:
                logger.error(
                    f"extended_move_to: {self.get_state('drone_id')} unable to take off during move_to..."
                )
                return False
            logger.info("move_to: Take off completed, beginning to movement segment...")

        self._zero_velocity()
        stop_result = await self._wait_for_condition(
            lambda: self.is_stopped(), timeout=TASK_TIMEOUT, interval=0.1
        )
        if not stop_result:
            logger.warning(
                "extended_move_to: Failed to stop prior to orienting drone..."
            )
            self._active_action = False
            return False
        else:
            logger.info(
                f"extended_move_to: {self.get_state('drone_id')} successfully stopped prior to orienting drone..."
            )

        if heading_mode == common_protocol.LocationHeadingMode.TO_TARGET:
            # Orients drone to fixed target bearing
            target_bearing = bearing
        else:
            # Orients drone along the flight path heading (face 'forward')
            target_bearing = path_heading = self.calculate_bearing(lat, lon)

        self._set_pose_target(None, None, target_bearing)
        result = await self._wait_for_condition(
            lambda: self.is_drone_oriented(), timeout=TASK_TIMEOUT, interval=0.1
        )
        if not result:
            logger.warning(
                f"{self.get_state('drone_id')} failed to orient to target bearing {target_bearing} prior to executing move..."
            )
            logger.warning(
                f"Current orientation bearing {self.get_state('attitude')['yaw']}"
            )
            self._active_action = False
            return False
        else:
            logger.info(f"Completed orientation to bearing {target_bearing}")

        self._set_position_target(lat, lon, altitude)
        result = self.partition_lateral_velocities(lateral_vel)
        if result is None:
            logger.error(
                "extended_move_to: Unable to partition lateral velocity value..."
            )
            self._active_action = False
            self._set_position_target(None, None, None)
            return False
        x_vel = result[0]
        y_vel = result[1]
        self._set_velocity_target(x_vel, y_vel, up_vel)
        self.set_flight_state(common_protocol.FlightStatus.MOVING)

        result = await self._wait_for_condition(
            lambda: self._check_position_reached(), timeout=MOVE_TIMEOUT, interval=0.1
        )
        current_position = self.get_current_position()

        if result:
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
            logger.info(
                f"{self.get_state('drone_id')} completed movement to position "
                f"({current_position[0]}, {current_position[1]}, {current_position[2]})"
            )
        else:
            self._zero_velocity()
            await self._wait_for_condition(
                lambda: self.is_stopped(), timeout=TASK_TIMEOUT, interval=0.1
            )
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
            logger.warning(
                f"{self.get_state('drone_id')} failed extended move to target position ({lat}, {lon}, {altitude})..."
            )
            logger.warning(
                f"Current position: ({current_position[0]}, {current_position[1]}, {current_position[2]})"
            )
        self._active_action = False
        return result

    async def set_target(self, gimbal_id, control_mode, pitch, roll, yaw):
        """
        Implements the rotational controls to adjust the poses of both drone and gimbal based on parameters given.
        Presumes that the gimbal yaw is "fixed" and implements yaw specifications by turning the entire drone prior
        to modifying the gimbal characteristics for pitch and roll changes.
        """
        if control_mode == "velocity":
            logger.info("set_target: Gimbal rotation without target not implemented")
            return False

        result = await self._register_pending_task()
        if not result:
            logger.warning(
                "set_target: Pending task already queued, unable to register take off command"
            )
            return False
        else:
            logger.info("set_target: Successfully registered task, beginning procedure")

        if control_mode == "position":
            self._set_gimbal_target(
                min(360, max(0, pitch)), min(360, max(0, roll)), min(360, max(0, yaw))
            )

        result = await self._wait_for_condition(
            lambda: self.is_gimbal_oriented(), timeout=TASK_TIMEOUT, interval=0.1
        )
        current_g_pose = self.get_state("gimbal_pose")
        if result:
            logger.info(
                f"{self.get_state('drone_id')} completed aligning gimbal {gimbal_id} to target. "
                f"Pitch: {current_g_pose['g_pitch']}, Roll: {current_g_pose['g_roll']}, Yaw: {current_g_pose['g_yaw']}"
            )
        else:
            logger.warning(
                f"{self.get_state('drone_id')} failed to align gimbal {gimbal_id} to target. "
                f"Pitch: {current_g_pose['g_pitch']}, Roll: {current_g_pose['g_roll']}, Yaw: {current_g_pose['g_yaw']}"
            )
        self._active_action = False
        return result

    async def return_to_home(self):
        """
        Implements the kinematic component changes required to simulate the SteelEagle move_to command via
        the usage of a position target. This variant does not allow specification of a velocity target and
        will attempt to take a least time course to the target point at maximum achievable velocity while
        avoiding position target overshoot. If pose adjustments are required to meet the requested orientation,
        they are made prior to executing movement.
        """
        logger.info("Initiating move to sequence...")
        if (
            self.check_flight_state(common_protocol.FlightStatus.LANDED)
            or self.check_flight_state(common_protocol.FlightStatus.LANDING)
            or self.check_flight_state(common_protocol.FlightStatus.IDLE)
        ):
            logger.warning(
                f"return_to_home: {self.get_state('drone_id')} unable to execute RTH command"
                "from ground. Take off first..."
            )
            return False

        result = await self._register_pending_task()
        if not result:
            logger.warning(
                "return_to_home: Pending task already queued, unable to register take off command"
            )
            return False
        else:
            logger.info(
                "return_to_home: Successfully registered task, beginning procedure"
            )

        self._zero_velocity()
        stop_result = await self._wait_for_condition(
            lambda: self.is_stopped(), timeout=TASK_TIMEOUT, interval=0.1
        )
        if not stop_result:
            logger.warning("return_to_home: Failed to stop prior to orienting drone...")
            self._active_action = False
            return False
        else:
            logger.info(
                f"{self.get_state('drone_id')} successfully stopped prior to orienting drone..."
            )

        home_pos = self.get_home_location()
        current_pos = self.get_current_position()
        target_bearing = self.calculate_bearing(home_pos[0], home_pos[1])
        self._set_pose_target(None, None, target_bearing)

        self.set_flight_state(common_protocol.FlightStatus.MOVING)
        result = await self._wait_for_condition(
            lambda: self.is_drone_oriented(), timeout=TASK_TIMEOUT, interval=0.1
        )
        if not result:
            logger.warning(
                f"{self.get_state('drone_id')} failed to orient to target bearing {target_bearing} prior to executing move..."
            )
            logger.warning(
                f"Current orientation bearing {self.get_state('attitude')['yaw']}"
            )
            self._active_action = False
            return False
        else:
            logger.info(f"Completed orientation to bearing {target_bearing}")

        self._set_position_target(home_pos[0], home_pos[1], current_pos[2])
        result = await self._wait_for_condition(
            lambda: self._check_position_reached(), timeout=None, interval=0.1
        )
        current_position = self.get_current_position()

        if result:
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
            logger.info(
                f"{self.get_state('drone_id')} completed movement to position "
                f"({current_position[0]}, {current_position[1]}, {current_position[2]})"
            )
        else:
            self._zero_velocity()
            await self._wait_for_condition(
                lambda: self.is_stopped(), timeout=TASK_TIMEOUT, interval=0.1
            )
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
            logger.warning(
                f"{self.get_state('drone_id')} failed to move to target position ({home_pos[0]}, {home_pos[1]}, {current_pos[2]})..."
            )
            logger.warning(
                f"Current position: ({current_position[0]}, {current_position[1]}, {current_position[2]})"
            )
            return result

        logger.info("return_to_home: Beginning descent procedure...")
        self.set_flight_state(common_protocol.FlightStatus.LANDING)
        self._set_position_target(home_pos[0], home_pos[1], home_pos[2])
        result = await self._wait_for_condition(
            lambda: self.is_landed(), timeout=TASK_TIMEOUT, interval=0.1
        )

        self._zero_velocity()
        stop_result = await self._wait_for_condition(
            lambda: self.is_stopped(), timeout=TASK_TIMEOUT, interval=0.1
        )

        if result and stop_result:
            self.set_flight_state(common_protocol.FlightStatus.LANDED)
            logger.info(f"{self.get_state('drone_id')} completed landing...")
        else:
            self.set_flight_state(common_protocol.FlightStatus.HOVERING)
            current_position = self.get_current_position()
            logger.warning(f"{self.get_state('drone_id')} failed to land...")
            logger.warning(
                f"Current position after failed attempt: ({current_position[0]}, "
                f"{current_position[1]}, {current_position[2]})"
            )
        self._active_action = False
        return result

    """ Getter, Setter, & Checker Methods """

    def set_home_location(self, lat, lon, alt):
        """
        Primarily used during drone initialization to store the starting location as the drone's home position.
        Latitude and longitude are represented in degrees as decimal numbers while altitude is represented in meters.
        """
        self.home_location = {"lat": lat, "lon": lon, "alt": alt}
        logger.info(f"Home location updated to ({lon}, {lat}) at elevation {alt}...")

    def _update_state(self, characteristic: str, value):
        """
        Generic internal state updater called by specific characteristic update methods
        to modify values contained within the drone's state dictionary. State is stored
        as characteristic_name: value/dictionary{component: values...}.
        """
        if characteristic not in self._state:
            logger.info(f"Adding {characteristic} to internal state...")
        self._state[characteristic] = value

    def check_flight_state(self, target_state) -> bool:
        """
        Compares the flight state condition given as a parameter against the drone's
        current flight state (common_pb.FlightStatus).
        """
        if target_state == self.get_state("flight_state"):
            return True
        return False

    def _check_target_active(self, target_type: str) -> bool:
        """
        Checks if the specified target type is currently "active." An active target is
        defined as a target in which all component values are set to non-None values.
        """
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
                logger.error(
                    f"_check_target_active: Invalid target type requested. Received {target_type}..."
                )
                return False
        return any(value is not None for value in target.values())

    def get_angular_velocity(self) -> float:
        """
        Used by the autopilot to retrieve the angular velocity trait of the drone for benchmark compliance.
        Angular velocity is not currently used by any aspect of the simulated drone.
        """
        return self.get_state("angular_velocity")

    def get_current_position(self) -> tuple[float | None, float | None, float | None]:
        """
        Retrieves the drone's current global position - one of several characterstics stored
        outside of the drone's internal state dict. Latitude and longitude are always represented
        in degrees as decimal values while altitude is always represented in meters.
        """
        try:
            return (
                self.current_position["lat"],
                self.current_position["lon"],
                self.current_position["alt"],
            )
        except:
            logger.error("Unable to retrieve current position...")
            return (None, None, None)

    def get_home_location(self):
        """
        Retrieves the stored home location for the drone. Set during drone initialization unless
        manually updated by an external controller.
        """
        try:
            return (
                self.home_location["lat"],
                self.home_location["lon"],
                self.home_location["alt"],
            )
        except:
            logger.error("Home location not set...")
            return None

    def get_state(self, characteristic: str):
        """
        Generic internal state retriever called by directly by other methods when retrieving
        kinematic values stored in the drone's internal state dict. State is stored
        as characteristic_name: value/dictionary{component: values...}.
        """
        if characteristic not in self._state:
            logger.error(
                f"{characteristic} not included in drone state. Unable to retrieve..."
            )
            return None
        return self._state[characteristic]

    def is_landed(self):
        """
        Used as a lambda to check for completion of the asynchronous movement component of
        the land task. Returns true only when the drone is stopped and at ground level or
        within the margin of error allowed by the ALT_MATCH_TOLERANCE constant.
        """
        current_pos = self.get_current_position()
        if self.is_stopped() and abs(current_pos[2]) <= ALT_MATCH_TOLERANCE:
            self.set_current_position(current_pos[0], current_pos[1], 0)
            self._set_position_target(None, None, None)
            return True
        return False

    def is_drone_oriented(self):
        """
        Used as a lambda to check for completion of the asynchronous drone alignment required
        by move_to, extended_move_to, and set_target. Returns true when all component values
        are at or within the margin of error controlled by POSE_TOLERANCE relative to the given
        pose target. When this condition occurs, this also zeros the drone's rotation rate values
        and clears the pose target to prevent drift.
        """
        attitude = self.get_state("attitude")
        if (
            abs(attitude["pitch"] - self._pose_target["pitch"]) > POSE_TOLERANCE
            or abs(attitude["roll"] - self._pose_target["roll"]) > POSE_TOLERANCE
            or abs(attitude["yaw"] - self._pose_target["yaw"]) > POSE_TOLERANCE
        ):
            return False
        self.set_attitude(
            self._pose_target["pitch"],
            self._pose_target["roll"],
            self._pose_target["yaw"],
        )
        self._set_drone_rotation(0, 0, 0)
        self._set_pose_target(None, None, None)
        return True

    def is_gimbal_oriented(self):
        """
        Used as a lambda to check for completion of the asynchronous gimbal alignment required
        by set_target. Returns true when all component values are at or within the margin of error
        controlled by POSE_TOLERANCE relative to the given gimbal target. When this condition
        occurs, this also zeros the gimbal's rotation rate values and clears the gimbal target.
        """
        gimbal_pose = self.get_state("gimbal_pose")
        if (
            abs(gimbal_pose["g_pitch"] - self._gimbal_target["g_pitch"])
            > POSE_TOLERANCE
            or abs(gimbal_pose["g_roll"] - self._gimbal_target["g_roll"])
            > POSE_TOLERANCE
            or abs(gimbal_pose["g_yaw"] - self._gimbal_target["g_yaw"]) > POSE_TOLERANCE
        ):
            return False
        self.set_gimbal_pose(
            self._gimbal_target["g_pitch"],
            self._gimbal_target["g_roll"],
            self._gimbal_target["g_yaw"],
        )
        self._set_gimbal_rotation(0, 0, 0)
        self._set_gimbal_target(None, None, None)
        return True

    def is_stopped(self):
        """
        Used as a lambda to check for zeroed velocity following either completion of a movement
        or cancellation/failure of an outstanding task. Returns true when all component values
        of the drone's velocity are at zero or within the margin of error controlled by the
        MATCH_TOLERANCE constant. Clears any existing velocity target and the velocity target
        flags, explicitly sets the velocity state values to 0 to prevent float drift, and zeroes
        the drone's acceleration values.
        """
        current_velocity = self.get_state("velocity")
        if (
            current_velocity is None
            or abs(current_velocity["speedX"]) > MATCH_TOLERANCE
            or abs(current_velocity["speedY"]) > MATCH_TOLERANCE
            or abs(current_velocity["speedZ"]) > MATCH_TOLERANCE
        ):
            return False
        self._set_velocity_target(None, None, None)
        self._clear_velocity_target_flags()
        self.set_velocity(0, 0, 0)
        self._set_acceleration(0, 0, 0)
        return True

    def is_takeoff_complete(self):
        """
        Used as a lambda to check for completion of the asynchronous movement component of the
        take_off task. Returns true once the drone is at the position target and stopped (contained
        within the check_position_reached method). Expects that the drone's flight status was
        updated prior to setting the position target to initiate movement. Does not modify
        drone state directly, though check_position_reached will clear position targets and set
        position target flags on success.
        """
        current_vel = self.get_state("velocity")
        current_pos = self.get_current_position()
        vel_target = self._velocity_target
        pos_target = self._position_target
        return self._check_position_reached() and self.check_flight_state(
            common_protocol.FlightStatus.TAKING_OFF
        )

    def is_task_lock_open(self):
        """
        Used as a lambda to check for the main event loop's movement of the registered task from
        pending status to active.
        """
        return not self._active_action

    """ Internal State Methods """

    def set_attitude(self, pitch: float, roll: float, yaw: float):
        """
        Assumes all component values are in degrees from 0-360
        """
        attitude = {"pitch": pitch, "roll": roll, "yaw": yaw}
        self._update_state("attitude", attitude)
        logger.debug(
            f"set_attitude: Drone attitude set to pitch: {pitch}, roll: {roll}, yaw: {yaw}"
        )

    def set_battery_percent(self, starting_charge: float):
        """
        Used by the update_kinematics method to simulate progressive drain on the drone's
        battery. Drain rates are specified by the LANDED_DRAIN_RATE and ACTIVE_DRAIN_RATE
        constants.
        """
        self._update_state("battery_percent", max(0, starting_charge))

    def set_current_position(self, new_lat: float, new_lon: float, new_alt: float):
        """
        Used by the update_kinematics method to simulate movement of the drone through 3-D
        space based on stored velocity values.
        """
        self.current_position.update(lat=new_lat, lon=new_lon, alt=new_alt)
        logger.debug(
            f"set_current_position: Current position set to ({new_lat}, {new_lon}, {new_alt})"
        )

    def set_flight_state(self, flight_state):
        """
        Changes the drone's current flight state. Expected values are contained within the
        common_pb2.FlightStatus enum.
        """
        self._update_state("flight_state", flight_state)
        logger.info(f"set_flight_state: Current flight state set to: {flight_state}")

    def set_gimbal_pose(self, pitch: float, roll: float, yaw: float):
        """
        Used by the update_kinematics method to simulate rotation of the drone's gimbal
        based on stored gimbal rotation rate values.
        """
        gimbal_pose = {"g_pitch": pitch, "g_roll": roll, "g_yaw": yaw}
        self._update_state("gimbal_pose", gimbal_pose)
        logger.debug(
            f"set_gimbal_pose: Gimbal pose set to g_pitch: {pitch}, g_roll: {roll}, g_yaw: {yaw}"
        )

    def set_magnetometer(self, condition_code: int):
        """
        Set during initialization for simulated telemetry. 0 = good, 1 = calibration, 2 = perturbation.
        Has no impact on the simulated drone's movement and position state.
        """
        self._update_state("magnetometer", condition_code)
        logger.info(f"Magnetometer reading updated to {condition_code}")

    def set_name(self, drone_id: str):
        """
        Set during initialization or if manually called by the controller to allow distinguishing
        between multiple simulated drones running simultaneously.
        """
        self._update_state("drone_id", drone_id)
        logger.info(f"Drone name set as: {drone_id}")

    def set_velocity(self, vel_x: float, vel_y: float, vel_z: float):
        """
        Used by the update_kinematics method to simulate the speed of the drone in 3-D space.
        Contributes to position modifications at each time step and is itself influenced by
        the drone's stored acceleration rates and the predefined maximal values (MAX_SPEED
        for x, y and MAX_CLIMB for z).
        """
        velocity = {
            "speedX": max(min(vel_x, MAX_SPEED), -MAX_SPEED),
            "speedY": max(min(vel_y, MAX_SPEED), -MAX_SPEED),
            "speedZ": max(min(vel_z, MAX_CLIMB), -MAX_CLIMB),
        }
        self._update_state("velocity", velocity)
        logger.debug(
            f"set_velocity: Drone velocity set to ("
            f"{velocity['speedX']}, {velocity['speedY']}, {velocity['speedZ']})"
        )

    def set_angular_velocity(self, angular_vel: float):
        """
        Used by the autopilot to set the angular velocity trait of the drone for benchmark compliance.
        Angular velocity is not currently used by any aspect of the simulated drone.
        """
        self._update_state("angular_velocity", angular_vel)
        logger.debug(f"set_angular_velocity: Angular velocity set to {angular_vel}")

    def set_satellites(self, satellite_count: int):
        """
        Set during initialization for simulated telemetry. May be modified by external calls
        to simulate various operational conditions. Has no impact on the simulated drone's
        movement and position state.
        """
        self._update_state("satellite_count", satellite_count)
        logger.info(f"GPS satellite count set to: {satellite_count}")

    def _set_acceleration(self, accX: float, accY: float, accZ: float):
        """
        Used by kinematics methods to modify the current acceleration rate. Primary state factor
        that controls the simulated movement of the drone and is expected to be updated multiple
        times in each iteration of the state_loop based on current conditions relative to the
        drone's position and velocity targets.
        """
        acceleration = {
            "accX": max(min(accX, MAX_ACCELERATION), -MAX_ACCELERATION),
            "accY": max(min(accY, MAX_ACCELERATION), -MAX_ACCELERATION),
            "accZ": max(min(accZ, MAX_ACCELERATION), -MAX_ACCELERATION),
        }
        self._update_state("acceleration", acceleration)
        logger.debug(
            f"_set_acceleration: Acceleration set to "
            f"({acceleration['accX']}, {acceleration['accY']}, {acceleration['accZ']})"
        )

    def _set_drone_rotation(self, pitch_rate: float, roll_rate: float, yaw_rate: float):
        """
        Used by kinematics methods to modify the current rotation rate for drone pose characteristics.
        Primary factor for simulating rotational movements of the drone during the state_loop.
        """
        rotation = {
            "pitch_rate": max(min(pitch_rate, MAX_ROTA_RATE), -MAX_ROTA_RATE),
            "roll_rate": max(min(roll_rate, MAX_ROTA_RATE), -MAX_ROTA_RATE),
            "yaw_rate": max(min(yaw_rate, MAX_YAW_RATE), -MAX_YAW_RATE),
        }
        self._update_state("drone_rotation_rates", rotation)
        logger.debug(
            f"_set_drone_rotation: Pose rotation rates set to "
            f"{rotation['pitch_rate']}, {rotation['roll_rate']}, {rotation['yaw_rate']}"
        )

    def _set_gimbal_rotation(
        self, g_pitch_rate: float, g_roll_rate: float, g_yaw_rate: float
    ):
        """
        Used by kinematics methods to modify the current rotation rate for gimbal pose characteristics.
        Primary factor for simulating rotational movements of the gimbal during the state_loop.
        """
        rotation = {
            "g_pitch_rate": max(min(g_pitch_rate, MAX_G_ROTA_RATE), -MAX_G_ROTA_RATE),
            "g_roll_rate": max(min(g_roll_rate, MAX_G_ROTA_RATE), -MAX_G_ROTA_RATE),
            "g_yaw_rate": max(min(g_yaw_rate, MAX_G_ROTA_RATE), -MAX_G_ROTA_RATE),
        }
        self._update_state("gimbal_rotation_rates", rotation)
        logger.debug(
            f"_set_gimbal_rotation: Gimbal rotation rates set to "
            f"{rotation['g_pitch_rate']}, {rotation['g_roll_rate']}, {rotation['g_yaw_rate']}"
        )

    def _clear_velocity_target_flags(self):
        """
        Convenience method to clear velocity target flags when overriding or deleting a velocity target.
        """
        self._x_vel_flag = False
        self._y_vel_flag = False
        self._z_vel_flag = False

    """ Kinematics Methods """

    def _calculate_acceleration_direction(self):
        """
        The first kinematic calculation call in the drone's state loop. Used to derive direction for
        acceleration based on the drone's current position and specified position target. It is
        expected that subsequent calls (check_braking_threshold, check_velocity_reached) will modify
        both magnitude and (potentially) sign of the values yielded by this method, which returns
        maximal values in the target direction based on the acceleration limit specified by
        MAX_ACCELERATION. Zeroes acceleration values if the drone is already at a maximal velocity
        in the given plane of movement.
        """
        current_position = self.get_current_position()
        velocity = self.get_state("velocity")
        if velocity is None:
            logger.error(
                "_calculate_acceleration_direction: Velocity state not initialized..."
            )
            return
        if (
            self._position_target["lat"] is None
            or self._position_target["lon"] is None
            or self._position_target["alt"] is None
        ):
            logger.error(
                "_calculate_acceleration_direction: Position target not set..."
            )
            logger.error(f"Target lat: {self._position_target['lat']}")
            logger.error(f"Target lon: {self._position_target['lon']}")
            logger.error(f"Target alt: {self._position_target['alt']}")
            return
        if (
            current_position[0] is None
            or current_position[1] is None
            or current_position[2] is None
        ):
            logger.error(
                "_calculate_acceleration_direction: Current position not set..."
            )
            logger.error(f"Current lat: {current_position[0]}")
            logger.error(f"Current lon: {current_position[1]}")
            logger.error(f"Current alt: {current_position[2]}")
            return
        if (
            velocity["speedX"] is None
            or velocity["speedY"] is None
            or velocity["speedZ"] is None
        ):
            logger.error(
                "_calculate_acceleration_direction: Velocity component(s) not set..."
            )
            logger.error(f"Current speedX: {velocity['speedX']}")
            logger.error(f"Current speedY: {velocity['speedY']}")
            logger.error(f"Current speedZ: {velocity['speedZ']}")
        else:
            d_lat = self._position_target["lat"] - current_position[0]
            d_lon = self._position_target["lon"] - current_position[1]
            d_alt = self._position_target["alt"] - current_position[2]
            if d_lat > 0 and velocity["speedX"] != MAX_SPEED:
                acc_x = MAX_ACCELERATION
            elif d_lat < 0 and velocity["speedX"] != -MAX_SPEED:
                acc_x = -MAX_ACCELERATION
            else:
                acc_x = 0
            if d_lon > 0 and velocity["speedY"] != MAX_SPEED:
                acc_y = MAX_ACCELERATION
            elif d_lon < 0 and velocity["speedY"] != -MAX_SPEED:
                acc_y = -MAX_ACCELERATION
            else:
                acc_y = 0
            if d_alt > 0 and velocity["speedZ"] != MAX_CLIMB:
                acc_z = MAX_ACCELERATION
            elif d_alt < 0 and velocity["speedZ"] != -MAX_CLIMB:
                acc_z = -MAX_ACCELERATION
            else:
                acc_z = 0

            logger.debug(
                "_calculate_acceleration_direction: Setting acceleration to "
                f"({acc_x}, {acc_y}, {acc_z})"
            )
            self._set_acceleration(acc_x, acc_y, acc_z)

    def calculate_bearing(self, lat: float, lon: float) -> float | None:
        """
        Uses the drone's current simulated position to calculate an estimated
        start bearing to the reference point provided as parameters. All values
        for latitude and longitude are in degrees as decimal numbers while the
        bearing produced is in degrees from 0-360.
        """
        current_position = self.get_current_position()
        if (
            current_position[0] is None
            or current_position[1] is None
            or current_position[2] is None
        ):
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
        theta = np.atan2(
            np.sin(d_lon) * np.cos(end_lat),
            np.cos(start_lat) * np.sin(end_lat)
            - np.sin(start_lat) * np.cos(end_lat) * np.cos(d_lon),
        )
        result = (np.rad2deg(theta) + 360) % 360
        return result

    def _calculate_deceleration(self, vel_val: float, dist_remaining: float):
        """
        Used by kinematic calculation methods to either prevent overshoot of a position
        target or assist in rapid stopping of the drone when a task is either canceled
        or failed (either producing a call to zero_velocity()). Passing a value of
        0 for dist_remaining signals intent to stop the drone as quickly as possible.
        Splits out the case of zero velocity in the target direction to prevent acceleration
        oscillation when moving over small distances at low speeds.
        """
        if dist_remaining == 0:
            return -np.sign(vel_val) * MAX_ACCELERATION
        # Prevent excessive breaking at low relative speeds
        elif vel_val == 0:
            return np.sign(dist_remaining) * MAX_ACCELERATION
        else:
            return -(vel_val**2) / (2 * dist_remaining)

    def _check_braking_thresholds(self):
        """
        Calculates the stopping distance required in each plane of movement given the drone's
        current velocity and acceleration rates and controls the braking process when the drone
        approaches its current position target. Adheres to velocity constraints if a velocity
        target is specified (such as during extended_move_to) until braking is required, at which
        point this method overrides the acceleration values set from earlier state_loop methods
        to prevent overshoot.
        """
        acceleration = self.get_state("acceleration")
        velocity = self.get_state("velocity")
        current_position = self.get_current_position()

        if acceleration is None or velocity is None:
            logger.error(
                "_check_braking_thresholds: Failed to retrieve drone velocity and acceleration"
            )
            logger.error(f"Velocity: {velocity}")
            logger.error(f"Acceleration: {acceleration}")
            return
        logger.debug(
            f"_check_braking_thresholds: Acceleration before check: "
            f"({acceleration['accX']}, {acceleration['accY']}, {acceleration['accZ']})"
        )
        if (
            self._position_target["lat"] is None
            or self._position_target["lon"] is None
            or self._position_target["alt"] is None
        ):
            logger.error("_check_braking_thresholds: Position target not set...")
            logger.error(f"Target lat: {self._position_target['lat']}")
            logger.error(f"Target lon: {self._position_target['lon']}")
            logger.error(f"Target alt: {self._position_target['alt']}")
            return
        if (
            current_position[0] is None
            or current_position[1] is None
            or current_position[2] is None
        ):
            logger.error("_check_braking_thresholds: Current position not set...")
            logger.error(f"Current lat: {current_position[0]}")
            logger.error(f"Current lon: {current_position[1]}")
            logger.error(f"Current alt: {current_position[2]}")
            return

        # Calculate distance values by fixing latitude and longitude for respective values.
        # Fixes current position longitude for x and target position latitude for y
        dist_x = self.haversine(
            current_position[0],
            current_position[1],
            self._position_target["lat"],
            current_position[1],
        )
        dist_y = self.haversine(
            self._position_target["lat"],
            current_position[1],
            self._position_target["lat"],
            self._position_target["lon"],
        )
        dist_z = self._position_target["alt"] - current_position[2]
        stop_distances = self.get_stop_distances()
        logger.debug(
            f"_check_braking_thresholds: Stop Distances: {stop_distances[0]}, {stop_distances[1]}, {stop_distances[2]}"
        )
        logger.debug(
            f"_check_braking_thresholds: Distances: X: {dist_x}, Y: {dist_y}, Z: {dist_z}"
        )

        # Begin braking when the stopping distance exceeds the current distance remaining estimate
        # or when distance remaining is small
        if stop_distances[0] > abs(dist_x) or abs(dist_x) < 1:
            acceleration["accX"] = self._calculate_deceleration(
                velocity["speedX"], dist_x
            )
        if stop_distances[1] > abs(dist_y) or abs(dist_y) < 1:
            acceleration["accY"] = self._calculate_deceleration(
                velocity["speedY"], dist_y
            )
        if stop_distances[2] > abs(dist_z) or abs(dist_z) < 1:
            acceleration["accZ"] = self._calculate_deceleration(
                velocity["speedZ"], dist_z
            )

        # Check for velocity constraints and ensure adherence until within braking distance
        if self._check_target_active("velocity"):
            if abs(velocity["speedX"]) >= abs(self._velocity_target["speedX"]):
                if np.sign(acceleration["accX"]) + np.sign(velocity["speedX"]) == 0:
                    self._x_vel_flag = False
                if np.sign(acceleration["accX"]) == np.sign(velocity["speedX"]):
                    acceleration["accX"] = 0
            if abs(velocity["speedY"]) >= abs(self._velocity_target["speedY"]):
                if np.sign(acceleration["accY"]) + np.sign(velocity["speedY"]) == 0:
                    self._y_vel_flag = False
                if np.sign(acceleration["accY"]) == np.sign(velocity["speedY"]):
                    acceleration["accY"] = 0
            if abs(velocity["speedZ"]) >= abs(self._velocity_target["speedZ"]):
                if np.sign(acceleration["accZ"]) + np.sign(velocity["speedZ"]) == 0:
                    self._z_vel_flag = False
                if np.sign(acceleration["accZ"]) == np.sign(velocity["speedZ"]):
                    acceleration["accZ"] = 0
            if not self._x_vel_flag and not self._y_vel_flag and not self._z_vel_flag:
                # Clear velocity target once all dimensions are decelerating/stopped
                self._set_velocity_target(None, None, None)

        logger.debug(
            "_calculate_acceleration_direction: Setting acceleration to "
            f"({acceleration['accX']}, {acceleration['accY']}, {acceleration['accZ']})"
        )
        self._set_acceleration(
            acceleration["accX"], acceleration["accY"], acceleration["accZ"]
        )

    def _check_drone_pose_reached(self):
        """
        Used by the state_loop to check for drone pose matches to the target pose. On match, zeroes
        the rotation rates and explicitly sets attitude components to prevent floating point drift.
        Does not clear the pose target, which is handled by the is_drone_oriented() method. Error
        tolerance specified by the constant POSE_TOLERANCE
        """
        pose = self.get_state("attitude")
        if (
            pose is None
            or pose["pitch"] is None
            or pose["roll"] is None
            or pose["yaw"] is None
        ):
            logger.error(
                "_check_drone_pose_reached: Failed to retrieve current drone pose..."
            )
            logger.error(f"Pose: {pose}")
            return
        if (
            self._pose_target["pitch"] is None
            or self._pose_target["roll"] is None
            or self._pose_target["yaw"] is None
        ):
            logger.error("_check_drone_pose_reached: Pose target not properly set...")
            logger.error(f"Pitch: {self._pose_target['pitch']}")
            logger.error(f"Roll: {self._pose_target['roll']}")
            logger.error(f"Yaw: {self._pose_target['yaw']}")
            return
        if (
            abs(self._pose_target["pitch"] - pose["pitch"]) <= POSE_TOLERANCE
            and abs(self._pose_target["roll"] - pose["roll"]) <= POSE_TOLERANCE
            and abs(self._pose_target["yaw"] - pose["yaw"]) <= POSE_TOLERANCE
        ):
            self.set_attitude(
                self._pose_target["pitch"],
                self._pose_target["roll"],
                self._pose_target["yaw"],
            )
            self._set_drone_rotation(0, 0, 0)
        return

    def _check_gimbal_pose_reached(self):
        """
        Used by the state_loop to check for gimbal pose matches to the target pose. On match, zeroes
        the rotation rates and explicitly sets attitude components to prevent floating point drift.
        Does not clear the pose target, which is handled by the is_gimbal_oriented() method.
        """
        g_pose = self.get_state("gimbal_pose")
        if (
            g_pose is None
            or g_pose["g_pitch"] is None
            or g_pose["g_roll"] is None
            or g_pose["g_yaw"] is None
        ):
            logger.error(
                "_check_gimbal_pose_reached: Failed to retrieve current gimbal pose..."
            )
            logger.error(f"Gimbal pose: {g_pose}")
            return
        if (
            self._gimbal_target["g_pitch"] is None
            or self._gimbal_target["g_roll"] is None
            or self._gimbal_target["g_yaw"] is None
        ):
            logger.error(
                "_check_gimbal_pose_reached: Gimbal pose target not properly set..."
            )
            logger.error(f"Gimbal pitch: {self._gimbal_target['g_pitch']}")
            logger.error(f"Gimbal roll: {self._gimbal_target['g_roll']}")
            logger.error(f"Gimbal yaw: {self._gimbal_target['g_yaw']}")
            return

        if (
            abs(self._gimbal_target["g_pitch"] - g_pose["g_pitch"]) <= POSE_TOLERANCE
            and abs(self._gimbal_target["g_roll"] - g_pose["g_roll"]) <= POSE_TOLERANCE
            and abs(self._gimbal_target["g_yaw"] - g_pose["g_yaw"]) <= POSE_TOLERANCE
        ):
            self.set_gimbal_pose(
                self._gimbal_target["g_pitch"],
                self._gimbal_target["g_roll"],
                self._gimbal_target["g_yaw"],
            )
            self._set_gimbal_rotation(0, 0, 0)
        return

    def _check_position_reached(self):
        """
        Used as a lambda for tasks involving position targets. Checks for matches within
        error thresholds specified by DEG_MATCH_TOLERANCE (lat, lon) and ALT_MATCH_TOLERANCE
        (altitude). On match, clears the current position target and sets the position_flag
        to prevent oscillation around the specified position while waiting for other conditionals.
        The position flag is reset to false each time a call is made to _set_position_target().
        """
        # Check for a previous call clearing the position target
        if self._position_flag:
            return True
        current_position = self.get_current_position()

        if (
            self._position_target["lat"] is None
            or self._position_target["lon"] is None
            or self._position_target["alt"] is None
        ):
            logger.error("_check_position_reached: Position target not set...")
            logger.error(f"Target lat: {self._position_target['lat']}")
            logger.error(f"Target lon: {self._position_target['lon']}")
            logger.error(f"Target alt: {self._position_target['alt']}")
            return False
        if (
            current_position[0] is None
            or current_position[1] is None
            or current_position[2] is None
        ):
            logger.error("_check_position_reached: Current position not set...")
            logger.error(f"Current lat: {current_position[0]}")
            logger.error(f"Current lon: {current_position[1]}")
            logger.error(f"Current alt: {current_position[2]}")
            return False

        if (
            abs(current_position[0] - self._position_target["lat"])
            <= DEG_MATCH_TOLERANCE
            and abs(current_position[1] - self._position_target["lon"])
            <= DEG_MATCH_TOLERANCE
            and abs(current_position[2] - self._position_target["alt"])
            <= ALT_MATCH_TOLERANCE
            and self.is_stopped()
        ):
            self.set_current_position(
                self._position_target["lat"],
                self._position_target["lon"],
                self._position_target["alt"],
            )
            self._set_position_target(None, None, None)
            self._position_flag = True
            logger.info(
                "_check_position_reached: Clearing position target due to position match..."
            )
            return True
        return False

    def _check_velocity_reached(self):
        """
        Checks for velocity matches to a specified velocity target when constraints are placed on the
        drone within an error factor controlled by the MATCH_TOLERANCE constant. Modifies acceleration
        values set by calculate_acceleration_direction() earlier in the state_loop to prevent exceeding
        the velocity target. Expects its own acceleration values to be overriden by the check_braking_
        distances call that succeeds it in the state_loop.
        """
        velocity = self.get_state("velocity")
        acceleration = self.get_state("acceleration")

        if acceleration is None or velocity is None:
            logger.error(
                "_check_velocity_reached: Failed to retrieve drone velocity and acceleration"
            )
            logger.error(f"Velocity: {velocity}")
            logger.error(f"Acceleration: {acceleration}")
            return
        vel_x = velocity["speedX"]
        vel_y = velocity["speedY"]
        vel_z = velocity["speedZ"]

        if vel_x is None or vel_y is None or vel_z is None:
            logger.error("_check_velocity_reached: Drone velocity not properly set...")
            logger.error(f"Drone x velocity: {vel_x}")
            logger.error(f"Drone y velocity: {vel_y}")
            logger.error(f"Drone z velocity: {vel_z}")
            return
        if (
            self._velocity_target["speedX"] is None
            or self._velocity_target["speedY"] is None
            or self._velocity_target["speedZ"] is None
        ):
            logger.error("_check_velocity_reached: Velocity target not properly set...")
            logger.error(f"Velocity speedX: {self._velocity_target['speedX']}")
            logger.error(f"Velocity speedY: {self._velocity_target['speedY']}")
            logger.error(f"Velocity speedZ: {self._velocity_target['speedZ']}")
            return

        if abs(vel_x - self._velocity_target["speedX"]) <= MATCH_TOLERANCE:
            acceleration["accX"] = 0
        if abs(vel_y - self._velocity_target["speedY"]) <= MATCH_TOLERANCE:
            acceleration["accY"] = 0
        if abs(vel_z - self._velocity_target["speedZ"]) <= MATCH_TOLERANCE:
            acceleration["accZ"] = 0
        # Explicitly locks velocity to target velocity to prevent floating point drift
        if (
            acceleration["accX"] == 0
            and acceleration["accY"] == 0
            and acceleration["accZ"] == 0
        ):
            self.set_velocity(
                self._velocity_target["speedX"],
                self._velocity_target["speedY"],
                self._velocity_target["speedZ"],
            )
        self._set_acceleration(
            acceleration["accX"], acceleration["accY"], acceleration["accZ"]
        )

    def _zero_velocity(self):
        """
        Sets a velocity target to zero the speed of the drone in all dimensions. Subsequent passes
        through the state_loop calculate appropriate acceleration values to stop the simulated drone.
        """
        self._set_velocity_target(0, 0, 0)
        current_velocity = self.get_state("velocity")

        if current_velocity is None:
            logger.error("_zero_velocity: Failed to retrieve current velocity...")
            logger.error(f"Current stored velocity: {current_velocity}")
            return
        if (
            current_velocity["speedX"] is None
            or current_velocity["speedY"] is None
            or current_velocity["speedZ"] is None
        ):
            logger.error("_zero_velocity: Component of velocity improperly set...")
            logger.error(f"Velocity speedX: {current_velocity['speedX']}")
            logger.error(f"Velocity speedY: {current_velocity['speedY']}")
            logger.error(f"Velocity speedZ: {current_velocity['speedZ']}")
            return

    def _set_gimbal_target(
        self,
        new_g_pitch: float | None,
        new_g_roll: float | None,
        new_g_yaw: float | None,
    ):
        """
        Sets and clears the gimbal target in the drone's internal state. When set to an active target,
        defined as having no None values, also sets rotation rates for the gimbal to trigger subsequent
        updates in the update_kinematics call.
        """
        current_g_pose = self.get_state("gimbal_pose")
        if any(value is not None for value in [new_g_pitch, new_g_roll, new_g_yaw]):
            if new_g_pitch is None:
                target_g_pitch = current_g_pose["g_pitch"]
            else:
                target_g_pitch = new_g_pitch
            if new_g_roll is None:
                target_g_roll = current_g_pose["g_roll"]
            else:
                target_g_roll = new_g_roll
            if new_g_yaw is None:
                target_g_yaw = current_g_pose["g_yaw"]
            else:
                target_g_yaw = new_g_yaw
        else:
            target_g_pitch = new_g_pitch
            target_g_roll = new_g_roll
            target_g_yaw = new_g_yaw
            logger.info("_set_gimbal_target: Clearing gimbal target...")

        if not self._check_target_active("gimbal"):
            self._set_gimbal_rotation(MAX_ROTA_RATE, MAX_ROTA_RATE, MAX_ROTA_RATE)

        self._gimbal_target.update(
            g_pitch=target_g_pitch, g_roll=target_g_roll, g_yaw=target_g_yaw
        )
        logger.debug(
            f"_set_gimbal_target: Gimbal pose target set to: "
            f"     Gimbal Pitch: {target_g_pitch}"
            f"     Gimbal Roll: {target_g_roll}"
            f"     Gimbal Yaw: {target_g_yaw}"
        )

    def _set_pose_target(
        self, new_pitch: float | None, new_roll: float | None, new_yaw: float | None
    ):
        """
        Sets and clears the drone pose target in the drone's internal state. When set to an active target,
        defined as having no None values, also sets rotation rates for the drone to trigger subsequent
        updates in the update_kinematics call.
        """
        current_pose = self.get_state("attitude")
        if any(value is not None for value in [new_pitch, new_roll, new_yaw]):
            if new_pitch is None:
                target_pitch = current_pose["pitch"]
            else:
                target_pitch = new_pitch
            if new_roll is None:
                target_roll = current_pose["roll"]
            else:
                target_roll = new_roll
            if new_yaw is None:
                target_yaw = current_pose["yaw"]
            else:
                target_yaw = new_yaw
        else:
            target_pitch = new_pitch
            target_roll = new_roll
            target_yaw = new_yaw
            logger.info("_set_pose_target: Clearing pose target...")

        if not self._check_target_active("pose"):
            self._set_drone_rotation(MAX_ROTA_RATE, MAX_ROTA_RATE, MAX_ROTA_RATE)

        self._pose_target.update(pitch=target_pitch, roll=target_roll, yaw=target_yaw)
        logger.debug(
            f"Pose target set to: "
            f"\n     Pitch: {target_pitch}"
            f"\n     Roll: {target_roll}"
            f"\n     Yaw: {target_yaw}"
        )

    def _set_position_target(
        self, pos_x: float | None, pos_y: float | None, pos_z: float | None
    ):
        """
        Sets and clears the position target in the drone's internal state. All calls to this method reset
        the position_flag read by is_position_reached() to false. Setting a position target is the primary
        mechanism to move the drone and is used in all SteelEagle API calls except set_target.
        """
        self._position_flag = False
        self._position_target.update(lat=pos_x, lon=pos_y, alt=pos_z)
        logger.debug(
            f"_set_position_target: Position target set to ({pos_x}, {pos_y}, {pos_z})"
        )

    def _set_velocity_target(
        self, vel_x: float | None, vel_y: float | None, vel_z: float | None
    ):
        """
        Sets and clears the velocity target in the drone's internal state. Calls that set an active velocity
        target, such as in extended_move_to or when stopping the drone through zero_velocity, reset component
        flags to True to allow velocity limiting through the check_velocity_reached method.
        """
        if vel_x is not None:
            x = max(min(vel_x, MAX_SPEED), -MAX_SPEED)
            self._x_vel_flag = True
        else:
            x = None
        if vel_y is not None:
            y = max(min(vel_y, MAX_SPEED), -MAX_SPEED)
            self._y_vel_flag = True
        else:
            y = None
        if vel_z is not None:
            z = max(min(vel_z, MAX_CLIMB), -MAX_CLIMB)
            self._z_vel_flag = True
        else:
            z = None

        self._velocity_target.update(speedX=x, speedY=y, speedZ=z)
        logger.debug(f"_set_velocity_target: Velocity target set to ({x}, {y}, {z})")

    def _update_kinematics(self):
        """
        Unifying mechanism for kinematics updates that reads the time elapsed since last update
        and passes the value to each subordinate update function, which in turn read their
        respective internal state values and change the drone's kinematic characteristics
        accordingly.
        """
        self.t_current = time.time()
        dt = self.t_current - self.t_last
        self._update_velocity(dt)
        self._update_position(dt)
        self._update_drone_pose(dt)
        self._update_gimbal_pose(dt)
        self._update_battery(dt)

    def _update_position(self, dt):
        """
        Uses the delta time produced by update_kinematics to calculate the change in the drone's
        simulated position based on current velocity values. Occurs after the drone's velocity
        has been updated at each time step.
        """
        prev_position = self.get_current_position()
        vel = self.get_state("velocity")

        if prev_position is None or vel is None:
            logger.error(
                "_update_position: Failed to retrieve current position and velocity..."
            )
            logger.error(f"Current position: {prev_position}")
            logger.error(f"Velocity: {vel}")
            return
        if (
            prev_position[0] is None
            or prev_position[1] is None
            or prev_position[2] is None
        ):
            logger.error("_update_position: Current position improperly set...")
            logger.error(f"Previous lat: {prev_position[0]}")
            logger.error(f"Previous lon: {prev_position[1]}")
            logger.error(f"Previous alt: {prev_position[2]}")
            return

        new_pos = self.get_new_latlon(
            prev_position[0], prev_position[1], dt * vel["speedX"], dt * vel["speedY"]
        )
        self.set_current_position(
            new_pos[0], new_pos[1], prev_position[2] + (dt * vel["speedZ"])
        )

    def _update_velocity(self, dt):
        """
        Uses the delta time produced by update_kinematics to calculate the change in the drone's
        simulated velocity based on current acceleration values. Occurs after target checks have
        refined acceleration values to meet the current desired state and before position updates
        occur in each time step.
        """
        dv = self.get_state("acceleration")
        prev_vel = self.get_state("velocity")

        if dv is None or prev_vel is None:
            logger.error(
                "_update_velocity: Failed to retrieve previous velocity and acceleration..."
            )
            logger.error(f"Previous velocity: {prev_vel}")
            logger.error(f"Previous acceleration: {dv}")
            return
        if (
            prev_vel["speedX"] is None
            or prev_vel["speedY"] is None
            or prev_vel["speedZ"] is None
        ):
            logger.error(
                "_update_velocity: Component of previous velocity improperly set..."
            )
            logger.error(f"Previous speedX: {prev_vel['speedX']}")
            logger.error(f"Previous speedY: {prev_vel['speedY']}")
            logger.error(f"Previous speedZ: {prev_vel['speedZ']}")
            return
        if dv["accX"] is None or dv["accY"] is None or dv["accZ"] is None:
            logger.error(
                "_update_velocity: Component of acceleration improperly set..."
            )
            logger.error(f"accX: {dv['accX']}")
            logger.error(f"accY: {dv['accY']}")
            logger.error(f"accZ: {dv['accZ']}")
            return

        self.set_velocity(
            prev_vel["speedX"] + (dt * dv["accX"]),
            prev_vel["speedY"] + (dt * dv["accY"]),
            prev_vel["speedZ"] + (dt * dv["accZ"]),
        )

    def _update_drone_pose(self, dt):
        """
        Uses the delta time produced by update_kinematics to calculate the change in the drone's
        simulated pose based on current rotational values. Checks for target value overshoot and
        explicitly constrains the value to the target value. Respective characteristic rotation
        rates are zeroed when this clamping occurs.
        """
        dp = self.get_state("drone_rotation_rates")
        prev_pose = self.get_state("attitude")

        if not self._check_target_active("pose"):
            return

        if dp is None or prev_pose is None:
            logger.error(
                "_update_drone_pose: Failed to retrieve prior drone pose and and rotation rates..."
            )
            logger.error(f"Previous pose: {prev_pose}")
            logger.error(f"Rotation rates: {dp}")
            return
        if (
            prev_pose["pitch"] is None
            or prev_pose["roll"] is None
            or prev_pose["yaw"] is None
        ):
            logger.error(
                "update_drone_pose: Component of previous pose improperly set..."
            )
            logger.error(f"Pitch: {prev_pose['pitch']}")
            logger.error(f"Roll: {prev_pose['roll']}")
            logger.error(f"Yaw: {prev_pose['yaw']}")
            return
        if (
            dp["pitch_rate"] is None
            or dp["roll_rate"] is None
            or dp["yaw_rate"] is None
        ):
            logger.error(
                "update_drone_pose: Component of pose rotation rate improperly set..."
            )
            logger.error(f"Pitch rate: {dp['pitch_rate']}")
            logger.error(f"Roll rate: {dp['roll_rate']}")
            logger.error(f"Yaw rate: {dp['yaw_rate']}")
            return

        update_rate_flag = False

        # Check for overshoot and constrain to pose target for each characteristic
        if (
            abs(self._pose_target["pitch"] - prev_pose["pitch"])
            <= dt * dp["pitch_rate"]
        ):
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
        logger.debug(f"_update_drone_pose: Drone pose set to: {pitch}, {roll}, {yaw}")

        if update_rate_flag:
            logger.debug("_update_drone_pose: Updating drone rotation rates...")
            self._set_drone_rotation(dp["pitch_rate"], dp["roll_rate"], dp["yaw_rate"])

    def _update_gimbal_pose(self, dt):
        """
        Uses the delta time produced by update_kinematics to calculate the change in the gimbals's
        simulated pose based on current rotational values. Checks for target value overshoot and
        explicitly constrains the value to the target value. Respective characteristic rotation
        rates are zeroed when this clamping occurs.
        """
        dp = self.get_state("gimbal_rotation_rates")
        prev_pose = self.get_state("gimbal_pose")

        if not self._check_target_active("gimbal"):
            return

        if dp is None or prev_pose is None:
            logger.error(
                "_update_gimbal_pose: Failed to retrieve previous gimbal pose and rotation rates..."
            )
            logger.error(f"Previous gimbal pose: {prev_pose}")
            logger.error(f"Gimbal rotation rates: {dp}")
            return
        if (
            prev_pose["g_pitch"] is None
            or prev_pose["g_roll"] is None
            or prev_pose["g_yaw"] is None
        ):
            logger.error(
                "_update_gimbal_pose: Component of previous gimbal pose improperly set..."
            )
            logger.error(f"Gimbal pitch: {prev_pose['g_pitch']}")
            logger.error(f"Gimbal roll: {prev_pose['g_roll']}")
            logger.error(f"Gimbal yaw: {prev_pose['g_yaw']}")
            return
        if (
            dp["g_pitch_rate"] is None
            or dp["g_roll_rate"] is None
            or dp["g_yaw_rate"] is None
        ):
            logger.error(
                "_update_gimbal_pose: Component of gimbal rotation rate improperly set..."
            )
            logger.error(f"Gimbal pitch rate: {dp['g_pitch_rate']}")
            logger.error(f"Gimbal roll rate: {dp['g_roll_rate']}")
            logger.error(f"Gimbal yaw rate: {dp['g_yaw_rate']}")
            return

        update_rate_flag = False
        # Check for overshoot and constrain to gimbal target for each characteristic
        if abs(self._gimbal_target["g_pitch"] - prev_pose["g_pitch"]) <= abs(
            dt * dp["g_pitch_rate"]
        ):
            dp["g_pitch_rate"] = 0
            g_pitch = self._gimbal_target["g_pitch"]
            update_rate_flag = True
        else:
            g_pitch = (prev_pose["g_pitch"] + (dt * dp["g_pitch_rate"])) % 360
        if abs(self._gimbal_target["g_roll"] - prev_pose["g_roll"]) <= abs(
            dt * dp["g_roll_rate"]
        ):
            dp["g_roll_rate"] = 0
            g_roll = self._gimbal_target["g_roll"]
            update_rate_flag = True
        else:
            g_roll = (prev_pose["g_roll"] + (dt * dp["g_roll_rate"])) % 360
        if abs(self._gimbal_target["g_yaw"] - prev_pose["g_yaw"]) <= abs(
            dt * dp["g_yaw_rate"]
        ):
            dp["g_yaw_rate"] = 0
            g_yaw = self._gimbal_target["g_yaw"]
            update_rate_flag = True
        else:
            g_yaw = (prev_pose["g_yaw"] + (dt * dp["g_yaw_rate"])) % 360

        self.set_gimbal_pose(g_pitch, g_roll, g_yaw)
        logger.debug(
            f"_update_gimbal_pose: Gimbal pose set to {g_pitch}, {g_roll}, {g_yaw}"
        )

        if update_rate_flag:
            logger.debug("_update_gimbal_pose: Updating gimbal rotation rates...")
            self._set_gimbal_rotation(
                dp["g_pitch_rate"], dp["g_roll_rate"], dp["g_yaw_rate"]
            )

    def _update_battery(self, dt):
        """
        Uses the delta time produced by update_kinematics to calculate the change in the drone's
        battery level based on the drone's current flight state. Draw rates are controlled by the
        LANDED_DRAIN_RATE and ACTIVE_DRAIN_RATE constants.
        """
        current_charge = self.get_state("battery_percent")
        current_state = self.get_state("flight_state")
        if (
            current_state == common_protocol.FlightStatus.LANDED
            or current_state == common_protocol.FlightStatus.IDLE
        ):
            new_charge = current_charge - dt * LANDED_DRAIN_RATE
        else:
            new_charge = current_charge - dt * ACTIVE_DRAIN_RATE
        self.set_battery_percent(new_charge)

    """ Math Utility Methods """

    def get_new_latlon(
        self, ref_lat: float, ref_lon: float, dist_x: float, dist_y: float
    ) -> tuple[float, float]:
        """
        Estimates the latitude and longitude of a new point from a reference given distances in the
        x and y dimensions.
        """
        new_lat = ref_lat + (dist_x / M_PER_LAT_DEG)
        m_per_deg_lon = np.cos(np.deg2rad(new_lat)) * M_PER_LAT_DEG
        new_lon = ref_lon + (dist_y / m_per_deg_lon)
        return (new_lat, new_lon)

    def haversine(
        self, origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float
    ) -> float:
        """
        Implementation of the haversine formula to calculate distance on a spherical object. Used to map
        distances between simulated points.
        """
        o_phi = np.deg2rad(origin_lat)
        r_phi = np.deg2rad(dest_lat)
        d_phi = np.deg2rad(dest_lat - origin_lat)
        d_lamba = np.deg2rad(dest_lon - origin_lon)

        a = np.power(np.sin(d_phi / 2.0), 2) + np.cos(o_phi) * np.cos(r_phi) * np.power(
            np.sin(d_lamba / 2.0), 2
        )
        c = 2 * np.atan2(np.sqrt(a), np.sqrt(1.0 - a))
        dist = EARTH_RADIUS_M * c

        return dist

    def calculate_stopping_times(
        self, vel_x: float, vel_y: float, vel_z: float
    ) -> list[float, float, float]:
        """
        Calculates the time required to stop the drone from given velocity components using the drone's
        maximal acceleration values.
        """
        return [
            abs(vel_x) / MAX_ACCELERATION,
            abs(vel_y) / MAX_ACCELERATION,
            abs(vel_z) / MAX_ACCELERATION,
        ]

    def calculate_distance_to_stop(
        self, stop_time: float, vel: float, acc: float
    ) -> float:
        """
        Given the stop time, acceleration rate, and current velocity, calculates the total
        distance in a single dimension traveled by the drone before brought to a stop respective
        to that plane.
        """
        return abs((vel * stop_time) + (0.5 * acc * stop_time**2))

    def get_stop_distances(self) -> list[float, float, float]:
        """
        Convenience function that combines calculate_stopping_times and calculate_distance_to_stop
        to produce the stopping distances in all three dimensions of travel.
        """
        velocity = self.get_state("velocity")
        stop_times = self.calculate_stopping_times(
            velocity["speedX"], velocity["speedY"], velocity["speedZ"]
        )
        d_x = self.calculate_distance_to_stop(
            stop_times[0],
            velocity["speedX"],
            np.sign(velocity["speedX"]) * -MAX_ACCELERATION,
        )
        d_y = self.calculate_distance_to_stop(
            stop_times[1],
            velocity["speedY"],
            np.sign(velocity["speedY"]) * -MAX_ACCELERATION,
        )
        d_z = self.calculate_distance_to_stop(
            stop_times[2],
            velocity["speedZ"],
            np.sign(velocity["speedZ"]) * -MAX_ACCELERATION,
        )
        return [d_x, d_y, d_z]

    def partition_lateral_velocities(self, lateral_vel) -> tuple[float, float] | None:
        """
        Calculates a proportional distribution of a singular lateral velocity across an
        x and y component based on the distances the drone is required to travel in both
        directions to reach the current position target.
        """
        current_pos = self.get_current_position()
        if (
            current_pos[0] is None
            or current_pos[1] is None
            or self._position_target is None
            or self._position_target["lat"] is None
            or self._position_target["lon"] is None
        ):
            logger.error(
                "partition_lateral_velocities: Component value improperly set..."
            )
            logger.error(
                f"Current lat: {current_pos[0]}, Current lon: {current_pos[1]}"
            )
            logger.error(
                f"Target lat: {self._position_target['lat']}, Target lon: {self._position_target['lon']}"
            )
            return None
        x_dist = self.haversine(
            current_pos[0], current_pos[1], self._position_target["lat"], current_pos[1]
        )
        y_dist = self.haversine(
            self._position_target["lat"],
            current_pos[1],
            self._position_target["lat"],
            self._position_target["lon"],
        )
        logger.info(f"x: {x_dist}, y: {y_dist}")
        total_dist = x_dist + y_dist
        if x_dist == 0:
            x_prop = 0
        else:
            x_prop = x_dist / total_dist
        if y_dist == 0:
            y_prop = 0
        else:
            y_prop = y_dist / total_dist
        return (lateral_vel * x_prop, lateral_vel * y_prop)
