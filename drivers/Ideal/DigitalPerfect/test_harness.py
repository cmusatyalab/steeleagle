from steeleagle_sdk.protocol.messages import telemetry_pb2 as telemetry_protocol
from steeleagle_sdk.protocol.services import control_service_pb2 as control_protocol
import numpy as np
import pytest
import SimulatedDrone
from SimulatedDrone import SimulatedDrone


@pytest.fixture
def drone_manager():
    return SimulatedDrone(ip="127.0.0.1")


def test_default_init(drone_manager: SimulatedDrone):
    assert drone_manager.get_state("drone_id") == "Simulated Drone"
    assert drone_manager._device_type == "Digital Drone"
    assert drone_manager.connection_ip == "127.0.0.1"
    assert not drone_manager.connection_state()
    assert drone_manager._takeoff_alt == 10
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")
    assert not drone_manager._pending_action
    assert not drone_manager._active_action
    assert not drone_manager._position_flag
    assert np.allclose(
        drone_manager.get_current_position(),
        [
            simulated_drone.DEFAULT_LAT,
            simulated_drone.DEFAULT_LON,
            simulated_drone.DEFAULT_ALT,
        ],
        rtol=1e-7,
        atol=1e-9,
    )


def test_starting_characteristics(drone_manager: SimulatedDrone):
    assert drone_manager.get_state("velocity") == {
        "speedX": 0.0,
        "speedY": 0.0,
        "speedZ": 0.0,
    }
    assert drone_manager.get_state("attitude") == {
        "pitch": 0.0,
        "roll": 0.0,
        "yaw": 0.0,
    }
    assert drone_manager.get_state("gimbal_pose") == {
        "g_pitch": 0.0,
        "g_roll": 0.0,
        "g_yaw": 0.0,
    }
    assert drone_manager.get_state("acceleration") == {
        "accX": 0.0,
        "accY": 0.0,
        "accZ": 0.0,
    }
    assert drone_manager.get_state("drone_rotation_rates") == {
        "pitch_rate": 0.0,
        "roll_rate": 0.0,
        "yaw_rate": 0.0,
    }
    assert drone_manager.get_state("gimbal_rotation_rates") == {
        "g_pitch_rate": 0.0,
        "g_roll_rate": 0.0,
        "g_yaw_rate": 0.0,
    }
    assert drone_manager.get_state("battery_percent") == 100
    assert (
        drone_manager.get_state("satellite_count") == simulated_drone.DEFAULT_SAT_COUNT
    )
    assert drone_manager.get_state("magnetometer") == 0


@pytest.mark.asyncio
async def test_connection_logic(drone_manager: SimulatedDrone):
    assert not drone_manager.connection_state()
    result = await drone_manager.connect()
    assert result
    assert drone_manager.connection_state()
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    result = await drone_manager.disconnect()
    assert result
    assert not drone_manager.connection_state()


@pytest.mark.asyncio
async def test_check_targets(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result

    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    drone_manager._set_position_target(0, 0, 0)
    drone_manager._set_velocity_target(1, 1, 1)
    drone_manager._set_pose_target(90, 90, 90)
    drone_manager._set_gimbal_target(90, 90, 90)

    assert drone_manager._check_target_active("position")
    assert drone_manager._check_target_active("velocity")
    assert drone_manager._check_target_active("pose")
    assert drone_manager._check_target_active("gimbal")

    result = await drone_manager.disconnect()
    assert result


@pytest.mark.asyncio
async def test_take_off(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    result = await drone_manager.take_off()
    assert result

    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [
            simulated_drone.DEFAULT_LAT,
            simulated_drone.DEFAULT_LON,
            drone_manager._takeoff_alt,
        ],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.disconnect()
    assert result


@pytest.mark.asyncio
async def test_land(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    result = await drone_manager.take_off()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    result = await drone_manager.land()
    assert result

    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [
            simulated_drone.DEFAULT_LAT,
            simulated_drone.DEFAULT_LON,
            simulated_drone.DEFAULT_ALT,
        ],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.disconnect()
    assert result


@pytest.mark.asyncio
async def test_move_to_same_loc(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    result = await drone_manager.take_off()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    current_pos = drone_manager.get_current_position()
    # No changes to drone state required for this move
    result = await drone_manager.move_to(
        current_pos[0],
        current_pos[1],
        current_pos[2],
        control_protocol.LocationHeadingMode.TO_TARGET,
        0,
    )
    assert result
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [
            simulated_drone.DEFAULT_LAT,
            simulated_drone.DEFAULT_LON,
            drone_manager._takeoff_alt,
        ],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    assert not drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.move_to(
        current_pos[0],
        current_pos[1],
        current_pos[2],
        control_protocol.LocationHeadingMode.TO_TARGET,
        180,
    )
    assert result
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [
            simulated_drone.DEFAULT_LAT,
            simulated_drone.DEFAULT_LON,
            drone_manager._takeoff_alt,
        ],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 180],
        rtol=1e-5,
        atol=1e-7,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.move_to(
        current_pos[0],
        current_pos[1],
        current_pos[2],
        control_protocol.LocationHeadingMode.HEADING_START,
        0,
    )
    assert result
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [
            simulated_drone.DEFAULT_LAT,
            simulated_drone.DEFAULT_LON,
            drone_manager._takeoff_alt,
        ],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.disconnect()
    assert result


@pytest.mark.asyncio
async def test_move_to_short(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    result = await drone_manager.take_off()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    target_latlon = drone_manager.get_new_latlon(
        simulated_drone.DEFAULT_LAT, simulated_drone.DEFAULT_LON, 10, 10
    )

    result = await drone_manager.move_to(
        target_latlon[0],
        target_latlon[1],
        drone_manager._takeoff_alt * 2,
        control_protocol.LocationHeadingMode.HEADING_START,
        None,
    )
    assert result
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.41377336153923, -79.9488056699767, drone_manager._takeoff_alt * 2],
        rtol=1e-1,
        atol=1e-1,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 45],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.land()
    assert result

    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.41377336153923, -79.9488056699767, simulated_drone.DEFAULT_ALT],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 45],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.disconnect()
    assert result


@pytest.mark.asyncio
async def test_move_to_long(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    result = await drone_manager.take_off()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    target_latlon = drone_manager.get_new_latlon(
        simulated_drone.DEFAULT_LAT, simulated_drone.DEFAULT_LON, -150, -200
    )

    result = await drone_manager.move_to(
        target_latlon[0],
        target_latlon[1],
        drone_manager._takeoff_alt * 2,
        control_protocol.LocationHeadingMode.HEADING_START,
        None,
    )
    assert result
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.4123338693042, -79.95128684675285, drone_manager._takeoff_alt * 2],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 233.13],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.land()
    assert result

    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.4123338693042, -79.95128684675285, simulated_drone.DEFAULT_ALT],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 233.13],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.disconnect()
    assert result


@pytest.mark.asyncio
async def test_move_to_multi_point(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    result = await drone_manager.take_off()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    target_latlon = drone_manager.get_new_latlon(
        simulated_drone.DEFAULT_LAT, simulated_drone.DEFAULT_LON, 10, 10
    )

    result = await drone_manager.move_to(
        target_latlon[0],
        target_latlon[1],
        drone_manager._takeoff_alt * 2,
        control_protocol.LocationHeadingMode.HEADING_START,
        None,
    )
    assert result
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.41377336153923, -79.9488056699767, drone_manager._takeoff_alt * 2],
        rtol=1e-1,
        atol=1e-1,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 45],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.move_to(
        simulated_drone.DEFAULT_LAT,
        simulated_drone.DEFAULT_LON,
        drone_manager._takeoff_alt,
        control_protocol.LocationHeadingMode.HEADING_START,
        None,
    )
    assert result

    current_pos = drone_manager.get_current_position()
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [
            simulated_drone.DEFAULT_LAT,
            simulated_drone.DEFAULT_LON,
            drone_manager._takeoff_alt,
        ],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 225],
        rtol=1e-5,
        atol=1e-7,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    target_latlon = drone_manager.get_new_latlon(
        simulated_drone.DEFAULT_LAT, simulated_drone.DEFAULT_LON, -150, -200
    )

    result = await drone_manager.move_to(
        target_latlon[0],
        target_latlon[1],
        drone_manager._takeoff_alt * 2,
        control_protocol.LocationHeadingMode.HEADING_START,
        None,
    )
    assert result
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.4123338693042, -79.95128684675285, drone_manager._takeoff_alt * 2],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 233.13],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.land()
    assert result

    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.4123338693042, -79.95128684675285, simulated_drone.DEFAULT_ALT],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 233.13],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.disconnect()
    assert result


@pytest.mark.asyncio
async def test_extended_move_to_same_point(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    result = await drone_manager.take_off()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    current_pos = drone_manager.get_current_position()
    # No changes to drone state required for this move
    result = await drone_manager.extended_move_to(
        current_pos[0],
        current_pos[1],
        current_pos[2],
        control_protocol.LocationHeadingMode.TO_TARGET,
        0,
        10,
        2,
        0,
    )
    assert result
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [
            simulated_drone.DEFAULT_LAT,
            simulated_drone.DEFAULT_LON,
            drone_manager._takeoff_alt,
        ],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.extended_move_to(
        current_pos[0],
        current_pos[1],
        current_pos[2],
        control_protocol.LocationHeadingMode.TO_TARGET,
        180,
        10,
        2,
        0,
    )
    assert result
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [
            simulated_drone.DEFAULT_LAT,
            simulated_drone.DEFAULT_LON,
            drone_manager._takeoff_alt,
        ],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 180],
        rtol=1e-5,
        atol=1e-7,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.extended_move_to(
        current_pos[0],
        current_pos[1],
        current_pos[2],
        control_protocol.LocationHeadingMode.HEADING_START,
        0,
        10,
        2,
        0,
    )
    assert result
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [
            simulated_drone.DEFAULT_LAT,
            simulated_drone.DEFAULT_LON,
            drone_manager._takeoff_alt,
        ],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.disconnect()
    assert result


@pytest.mark.asyncio
async def test_extended_move_to_short(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    result = await drone_manager.take_off()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    target_latlon = drone_manager.get_new_latlon(
        simulated_drone.DEFAULT_LAT, simulated_drone.DEFAULT_LON, 10, 10
    )

    result = await drone_manager.extended_move_to(
        target_latlon[0],
        target_latlon[1],
        drone_manager._takeoff_alt * 2,
        control_protocol.LocationHeadingMode.HEADING_START,
        None,
        10,
        3,
        0,
    )
    assert result
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.41377336153923, -79.9488056699767, drone_manager._takeoff_alt * 2],
        rtol=1e-1,
        atol=1e-1,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 45],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.land()
    assert result

    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.41377336153923, -79.9488056699767, simulated_drone.DEFAULT_ALT],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 45],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.disconnect()
    assert result


@pytest.mark.asyncio
async def test_extended_move_to_long(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    result = await drone_manager.take_off()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    target_latlon = drone_manager.get_new_latlon(
        simulated_drone.DEFAULT_LAT, simulated_drone.DEFAULT_LON, -150, -200
    )

    result = await drone_manager.extended_move_to(
        target_latlon[0],
        target_latlon[1],
        drone_manager._takeoff_alt * 2,
        control_protocol.LocationHeadingMode.HEADING_START,
        None,
        10,
        3,
        0,
    )
    assert result
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.4123338693042, -79.95128684675285, drone_manager._takeoff_alt * 2],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 233.13],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.land()
    assert result

    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.4123338693042, -79.95128684675285, simulated_drone.DEFAULT_ALT],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 233.13],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.disconnect()
    assert result


@pytest.mark.asyncio
async def test_extended_move_to_multi_point(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    result = await drone_manager.take_off()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    target_latlon = drone_manager.get_new_latlon(
        simulated_drone.DEFAULT_LAT, simulated_drone.DEFAULT_LON, 10, 10
    )

    result = await drone_manager.extended_move_to(
        target_latlon[0],
        target_latlon[1],
        drone_manager._takeoff_alt * 2,
        control_protocol.LocationHeadingMode.HEADING_START,
        None,
        10,
        3,
        0,
    )
    assert result
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.41377336153923, -79.9488056699767, drone_manager._takeoff_alt * 2],
        rtol=1e-1,
        atol=1e-1,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 45],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.extended_move_to(
        simulated_drone.DEFAULT_LAT,
        simulated_drone.DEFAULT_LON,
        drone_manager._takeoff_alt,
        control_protocol.LocationHeadingMode.HEADING_START,
        None,
        10,
        3,
        0,
    )
    assert result

    current_pos = drone_manager.get_current_position()
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [
            simulated_drone.DEFAULT_LAT,
            simulated_drone.DEFAULT_LON,
            drone_manager._takeoff_alt,
        ],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 225],
        rtol=1e-5,
        atol=1e-7,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    target_latlon = drone_manager.get_new_latlon(
        simulated_drone.DEFAULT_LAT, simulated_drone.DEFAULT_LON, -150, -200
    )

    result = await drone_manager.extended_move_to(
        target_latlon[0],
        target_latlon[1],
        drone_manager._takeoff_alt * 2,
        control_protocol.LocationHeadingMode.HEADING_START,
        None,
        10,
        3,
        0,
    )
    assert result
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.4123338693042, -79.95128684675285, drone_manager._takeoff_alt * 2],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 233.13],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.land()
    assert result

    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.4123338693042, -79.95128684675285, simulated_drone.DEFAULT_ALT],
        rtol=1e-5,
        atol=1e-7,
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 233.13],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )
    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )
    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    result = await drone_manager.disconnect()
    assert result


@pytest.mark.asyncio
async def test_set_target_no_change(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    result = await drone_manager.take_off()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    result = await drone_manager.set_target(0, "velocity", 0, 0, 0)
    assert not result

    result = await drone_manager.set_target(0, "position", 0, 0, 0)
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )

    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )

    result = await drone_manager.land()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [
            simulated_drone.DEFAULT_LAT,
            simulated_drone.DEFAULT_LON,
            simulated_drone.DEFAULT_ALT,
        ],
        rtol=1e-5,
        atol=1e-7,
    )


@pytest.mark.asyncio
async def test_set_target_yaw_only(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    result = await drone_manager.take_off()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    result = await drone_manager.set_target(0, "position", 0, 0, 90)
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 90],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )

    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )

    result = await drone_manager.land()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [
            simulated_drone.DEFAULT_LAT,
            simulated_drone.DEFAULT_LON,
            simulated_drone.DEFAULT_ALT,
        ],
        rtol=1e-5,
        atol=1e-7,
    )


@pytest.mark.asyncio
async def test_set_target_without_yaw(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    result = await drone_manager.take_off()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    result = await drone_manager.set_target(0, "position", 60, 30, 0)
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [60, 30, 0],
        rtol=1e-1,
        atol=1e-1,
    )

    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )

    result = await drone_manager.land()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [
            simulated_drone.DEFAULT_LAT,
            simulated_drone.DEFAULT_LON,
            simulated_drone.DEFAULT_ALT,
        ],
        rtol=1e-5,
        atol=1e-7,
    )


@pytest.mark.asyncio
async def test_set_target_all_aspects(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    result = await drone_manager.take_off()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    result = await drone_manager.set_target(0, "position", 60, 30, 215)
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.IDLE)

    attitude = drone_manager.get_state("attitude")
    assert attitude is not None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 215],
        rtol=1e-1,
        atol=1e-1,
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose is not None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [60, 30, 0],
        rtol=1e-1,
        atol=1e-1,
    )

    assert not drone_manager._check_target_active("position")
    assert not drone_manager._check_target_active("velocity")
    assert not drone_manager._check_target_active("pose")
    assert not drone_manager._check_target_active("gimbal")

    assert not drone_manager._active_action
    assert not drone_manager._pending_action
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7,
    )

    result = await drone_manager.land()
    assert result
    assert drone_manager.check_flight_state(telemetry_protocol.MotionStatus.MOTORS_OFF)
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [
            simulated_drone.DEFAULT_LAT,
            simulated_drone.DEFAULT_LON,
            simulated_drone.DEFAULT_ALT,
        ],
        rtol=1e-5,
        atol=1e-7,
    )