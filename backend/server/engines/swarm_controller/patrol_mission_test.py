from swarm_controller import PatrolArea, PatrolMission
import pytest_asyncio
import pytest

@pytest.mark.asyncio
async def test_mission_creation():
    patrol_area_list = await PatrolArea.load_from_file('test')
    print(patrol_area_list)

    drone_list = ['d1','d2','d3']
    mission = PatrolMission(drone_list, patrol_area_list)
    state = mission.get_state()

    assert len(state.drone_list) == 3
    assert len(state.patrol_area_list) == 1
    assert state.current_patrol_area is not None
    assert state.drone_list == drone_list

    patrol_area = state.patrol_area_list[0]
    patrol_waypoints = patrol_area.get_patrol_waypoints()
    assert len(patrol_waypoints) == 25
    for idx, patrol_waypoint in enumerate(patrol_waypoints):
        assert patrol_waypoint.waypoints == f"Hex.Hex_{idx+1}"

    drone_id, waypoints = mission.state_transition('d1', None)
    assert drone_id == 'd1'
    assert waypoints.waypoints == f"Hex.Hex_1"

    drone_id, waypoints = mission.state_transition('d1', None)
    assert drone_id == 'd1'
    assert waypoints.waypoints == f"Hex.Hex_2"

    drone_id, waypoints = mission.state_transition('d2', None)
    assert drone_id == 'd2'
    assert waypoints.waypoints == f"Hex.Hex_9"

    drone_id, waypoints = mission.state_transition('d3', None)
    assert drone_id == 'd3'
    assert waypoints.waypoints == f"Hex.Hex_17"

    for i in range(8):
        drone_id, waypoints = mission.state_transition('d3', None)
        assert drone_id == 'd3'
        assert waypoints.waypoints == f"Hex.Hex_{17+i+1}"

    drone_id, waypoints = mission.state_transition('d3', None)
    assert drone_id == 'd3'
    assert waypoints.waypoints == f"Hex.Hex_3"

    for i in range(5):
        drone_id, waypoints = mission.state_transition('d3', None)
        assert drone_id == 'd3'
        assert waypoints.waypoints == f"Hex.Hex_{4+i}"

    for i in range(7):
        drone_id, waypoints = mission.state_transition('d3', None)
        assert drone_id == 'd3'
        assert waypoints.waypoints == f"Hex.Hex_{10+i}"

    drone_id, waypoints = mission.state_transition('d3', None)
    assert drone_id == 'd3'
    assert waypoints == "finish"

