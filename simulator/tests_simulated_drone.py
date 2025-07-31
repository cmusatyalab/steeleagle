from simulated_drone import SimulatedDrone
import simulated_drone
import numpy as np
import pytest
import time

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

def test_connection_logic(drone_manager: SimulatedDrone):
    assert drone_manager.connection_state() == False
    assert drone_manager.connect() == True
    assert drone_manager.connection_state() == True
    assert drone_manager._active_action == False
    assert drone_manager._pending_action == False
    assert drone_manager.disconnect() == True
    assert drone_manager.connection_state() == False

def test_check_targets(drone_manager: SimulatedDrone):
    drone_manager.connect()
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
    drone_manager.disconnect()