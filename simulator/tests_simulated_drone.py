from simulated_drone import SimulatedDrone
import simulated_drone
import numpy as np
import pytest
import asyncio
import time
import common_pb2 as common_protocol

@pytest.fixture
def drone_manager():
    return SimulatedDrone(ip="127.0.0.1")

def test_default_init(drone_manager: SimulatedDrone):
    assert drone_manager.get_state("drone_id") == "Simulated Drone"
    assert drone_manager._device_type == "Digital Drone"
    assert drone_manager.connection_ip == "127.0.0.1"
    assert drone_manager.connection_state() == False
    assert drone_manager._takeoff_alt == 10
    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False
    assert drone_manager._pending_action == False
    assert drone_manager._active_action == False
    assert drone_manager._position_flag == False
    assert np.allclose(
        drone_manager.get_current_position(),
        [simulated_drone.DEFAULT_LAT,
        simulated_drone.DEFAULT_LON,
        simulated_drone.DEFAULT_ALT],
        rtol=1e-7,
        atol=1e-9
    )

def test_starting_characteristics(drone_manager: SimulatedDrone):
    assert drone_manager.get_state("velocity") == {
        "speedX": 0.0, "speedY": 0.0, "speedZ": 0.0}
    assert drone_manager.get_state("attitude") == {
        "pitch": 0.0, "roll": 0.0, "yaw": 0.0
    }
    assert drone_manager.get_state("gimbal_pose") == {
        "g_pitch": 0.0, "g_roll": 0.0, "g_yaw": 0.0
    }
    assert drone_manager.get_state("acceleration") == {
        "accX": 0.0, "accY": 0.0, "accZ": 0.0
    }
    assert drone_manager.get_state("drone_rotation_rates") == {
        "pitch_rate": 0.0, "roll_rate": 0.0, "yaw_rate": 0.0
    }
    assert drone_manager.get_state("gimbal_rotation_rates") == {
        "g_pitch_rate": 0.0, "g_roll_rate": 0.0, "g_yaw_rate": 0.0
    }
    assert drone_manager.get_state("battery_percent") == 100
    assert drone_manager.get_state("satellite_count") == simulated_drone.DEFAULT_SAT_COUNT
    assert drone_manager.get_state("magnetometer") == 0

@pytest.mark.asyncio
async def test_connection_logic(drone_manager: SimulatedDrone):
    assert drone_manager.connection_state() == False
    result = await drone_manager.connect()
    assert result == True
    assert drone_manager.connection_state() == True
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    result = await drone_manager.disconnect()
    assert result == True
    assert drone_manager.connection_state() == False

@pytest.mark.asyncio
async def test_check_targets(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result == True

    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False

    drone_manager._set_position_target(0, 0, 0)
    drone_manager._set_velocity_target(1, 1, 1)
    drone_manager._set_pose_target(90, 90, 90)
    drone_manager._set_gimbal_target(90, 90, 90)

    assert drone_manager._check_target_active("position") == True
    assert drone_manager._check_target_active("velocity") == True
    assert drone_manager._check_target_active("pose") == True
    assert drone_manager._check_target_active("gimbal") == True
    
    result = await drone_manager.disconnect()
    assert result == True

@pytest.mark.asyncio
async def test_take_off(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result == True
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.LANDED)
    result = await drone_manager.take_off()
    assert result == True
    
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [simulated_drone.DEFAULT_LAT,
         simulated_drone.DEFAULT_LON,
         drone_manager._takeoff_alt],
        rtol=1e-5,
        atol=1e-7
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude != None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose != None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)
    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False

    result = await drone_manager.disconnect()
    assert result == True

@pytest.mark.asyncio
async def test_land(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result == True
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.LANDED)
    result = await drone_manager.take_off()
    assert result == True
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)

    result = await drone_manager.land()
    assert result == True

    assert drone_manager.check_flight_state(common_protocol.FlightStatus.LANDED)
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [simulated_drone.DEFAULT_LAT,
         simulated_drone.DEFAULT_LON,
         simulated_drone.DEFAULT_ALT],
        rtol=1e-5,
        atol=1e-7
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude != None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose != None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False

    result = await drone_manager.disconnect()
    assert result == True

@pytest.mark.asyncio
async def test_move_to_same_loc(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result == True
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.LANDED)
    result = await drone_manager.take_off()
    assert result == True
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)
    
    current_pos = drone_manager.get_current_position()
    # No changes to drone state required for this move
    result = await drone_manager.move_to(current_pos[0], current_pos[1], current_pos[2],
                                         common_protocol.LocationHeadingMode.TO_TARGET, 0)
    assert result == True
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [simulated_drone.DEFAULT_LAT,
         simulated_drone.DEFAULT_LON,
         drone_manager._takeoff_alt],
        rtol=1e-5,
        atol=1e-7
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude != None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose != None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)
    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False

    result = await drone_manager.move_to(current_pos[0], current_pos[1], current_pos[2],
                                         common_protocol.LocationHeadingMode.TO_TARGET, 180)
    assert result == True
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [simulated_drone.DEFAULT_LAT,
         simulated_drone.DEFAULT_LON,
         drone_manager._takeoff_alt],
        rtol=1e-5,
        atol=1e-7
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude != None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 180],
        rtol=1e-5,
        atol=1e-7
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose != None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)
    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False

    result = await drone_manager.move_to(current_pos[0], current_pos[1], current_pos[2],
                                         common_protocol.LocationHeadingMode.HEADING_START, 0)
    assert result == True
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [simulated_drone.DEFAULT_LAT,
         simulated_drone.DEFAULT_LON,
         drone_manager._takeoff_alt],
        rtol=1e-5,
        atol=1e-7
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude != None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose != None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)
    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False

    result = await drone_manager.disconnect()
    assert result == True


@pytest.mark.asyncio
async def test_move_to_short(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result == True
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.LANDED)
    result = await drone_manager.take_off()
    assert result == True
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)


    target_latlon = drone_manager.get_new_latlon(simulated_drone.DEFAULT_LAT,
                                                 simulated_drone.DEFAULT_LON, 10, 10)

    result = await drone_manager.move_to(target_latlon[0], target_latlon[1], drone_manager._takeoff_alt * 2,
                                   common_protocol.LocationHeadingMode.HEADING_START, None)
    assert result == True
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.41377336153923, -79.9488056699767, drone_manager._takeoff_alt * 2],
        rtol=1e-1,
        atol=1e-1
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude != None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 45],
        rtol=1e-1,
        atol=1e-1
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose != None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1
    )
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)
    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False

    result = await drone_manager.land()
    assert result == True

    assert drone_manager.check_flight_state(common_protocol.FlightStatus.LANDED)
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.41377336153923, -79.9488056699767, simulated_drone.DEFAULT_ALT],
        rtol=1e-5,
        atol=1e-7
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude != None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 45],
        rtol=1e-1,
        atol=1e-1
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose != None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1
    )
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False

    result = await drone_manager.disconnect()
    assert result == True


@pytest.mark.asyncio
async def test_move_to_long(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result == True
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.LANDED)
    result = await drone_manager.take_off()
    assert result == True
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)

    target_latlon = drone_manager.get_new_latlon(simulated_drone.DEFAULT_LAT,
                                                 simulated_drone.DEFAULT_LON, -150, -200)

    result = await drone_manager.move_to(target_latlon[0], target_latlon[1], drone_manager._takeoff_alt * 2,
                                   common_protocol.LocationHeadingMode.HEADING_START, None)
    assert result == True
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.4123338693042, -79.95128684675285, drone_manager._takeoff_alt * 2],
        rtol=1e-5,
        atol=1e-7
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude != None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 233.13],
        rtol=1e-1,
        atol=1e-1
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose != None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1
    )
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)
    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False

    result = await drone_manager.land()
    assert result == True

    assert drone_manager.check_flight_state(common_protocol.FlightStatus.LANDED)
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.4123338693042, -79.95128684675285, simulated_drone.DEFAULT_ALT],
        rtol=1e-5,
        atol=1e-7
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude != None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 233.13],
        rtol=1e-1,
        atol=1e-1
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose != None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1
    )
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False

    result = await drone_manager.disconnect()
    assert result == True

@pytest.mark.asyncio
async def test_move_to_multi_point(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result == True
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.LANDED)
    result = await drone_manager.take_off()
    assert result == True
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)

    target_latlon = drone_manager.get_new_latlon(simulated_drone.DEFAULT_LAT,
                                                 simulated_drone.DEFAULT_LON, 10, 10)

    result = await drone_manager.move_to(target_latlon[0], target_latlon[1], drone_manager._takeoff_alt * 2,
                                   common_protocol.LocationHeadingMode.HEADING_START, None)
    assert result == True
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.41377336153923, -79.9488056699767, drone_manager._takeoff_alt * 2],
        rtol=1e-1,
        atol=1e-1
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude != None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 45],
        rtol=1e-1,
        atol=1e-1
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose != None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1
    )
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)
    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False

    result = await drone_manager.move_to(simulated_drone.DEFAULT_LAT, simulated_drone.DEFAULT_LON, drone_manager._takeoff_alt,
                                   common_protocol.LocationHeadingMode.HEADING_START, None)
    assert result == True

    current_pos = drone_manager.get_current_position()
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [simulated_drone.DEFAULT_LAT,
         simulated_drone.DEFAULT_LON,
         drone_manager._takeoff_alt],
        rtol=1e-5,
        atol=1e-7
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude != None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 225],
        rtol=1e-5,
        atol=1e-7
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose != None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)
    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False

    target_latlon = drone_manager.get_new_latlon(simulated_drone.DEFAULT_LAT,
                                                 simulated_drone.DEFAULT_LON, -150, -200)

    result = await drone_manager.move_to(target_latlon[0], target_latlon[1], drone_manager._takeoff_alt * 2,
                                   common_protocol.LocationHeadingMode.HEADING_START, None)
    assert result == True
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.4123338693042, -79.95128684675285, drone_manager._takeoff_alt * 2],
        rtol=1e-5,
        atol=1e-7
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude != None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 233.13],
        rtol=1e-1,
        atol=1e-1
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose != None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1
    )
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)
    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False

    result = await drone_manager.land()
    assert result == True

    assert drone_manager.check_flight_state(common_protocol.FlightStatus.LANDED)
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [40.4123338693042, -79.95128684675285, simulated_drone.DEFAULT_ALT],
        rtol=1e-5,
        atol=1e-7
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude != None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 233.13],
        rtol=1e-1,
        atol=1e-1
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose != None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-1,
        atol=1e-1
    )
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    velocity = drone_manager.get_state("velocity")
    assert np.allclose(
        [velocity["speedX"], velocity["speedY"], velocity["speedZ"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False

    result = await drone_manager.disconnect()
    assert result == True

@pytest.mark.asyncio
async def test_extended_move_to_same_point(drone_manager: SimulatedDrone):
    result = await drone_manager.connect()
    assert result == True
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.LANDED)
    result = await drone_manager.take_off()
    assert result == True
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)
    
    current_pos = drone_manager.get_current_position()
    # No changes to drone state required for this move
    result = await drone_manager.extended_move_to(current_pos[0], current_pos[1], current_pos[2],
                                         common_protocol.LocationHeadingMode.TO_TARGET, 0, 10, 2, 0)
    assert result == True
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [simulated_drone.DEFAULT_LAT,
         simulated_drone.DEFAULT_LON,
         drone_manager._takeoff_alt],
        rtol=1e-5,
        atol=1e-7
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude != None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose != None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)
    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False

    result = await drone_manager.extended_move_to(current_pos[0], current_pos[1], current_pos[2],
                                         common_protocol.LocationHeadingMode.TO_TARGET, 180, 10, 2, 0)
    assert result == True
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [simulated_drone.DEFAULT_LAT,
         simulated_drone.DEFAULT_LON,
         drone_manager._takeoff_alt],
        rtol=1e-5,
        atol=1e-7
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude != None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 180],
        rtol=1e-5,
        atol=1e-7
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose != None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)
    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False

    result = await drone_manager.extended_move_to(current_pos[0], current_pos[1], current_pos[2],
                                         common_protocol.LocationHeadingMode.HEADING_START, 0, 10, 2, 0)
    assert result == True
    current_pos = drone_manager.get_current_position()
    assert None not in current_pos
    assert np.allclose(
        [current_pos[0], current_pos[1], current_pos[2]],
        [simulated_drone.DEFAULT_LAT,
         simulated_drone.DEFAULT_LON,
         drone_manager._takeoff_alt],
        rtol=1e-5,
        atol=1e-7
    )
    attitude = drone_manager.get_state("attitude")
    assert attitude != None
    assert np.allclose(
        [attitude["pitch"], attitude["roll"], attitude["yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    gimbal_pose = drone_manager.get_state("gimbal_pose")
    assert gimbal_pose != None
    assert np.allclose(
        [gimbal_pose["g_pitch"], gimbal_pose["g_roll"], gimbal_pose["g_yaw"]],
        [0, 0, 0],
        rtol=1e-5,
        atol=1e-7
    )
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    assert drone_manager.check_flight_state(common_protocol.FlightStatus.HOVERING)
    assert drone_manager._check_target_active("position") == False
    assert drone_manager._check_target_active("velocity") == False
    assert drone_manager._check_target_active("pose") == False
    assert drone_manager._check_target_active("gimbal") == False

    result = await drone_manager.disconnect()
    assert result == True