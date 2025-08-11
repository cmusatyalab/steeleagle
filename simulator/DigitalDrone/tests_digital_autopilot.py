import anafi_perfect
import common_pb2 as common_protocol
import numpy as np
import pytest
from anafi_perfect import DigitalPerfectDrone

TOLERANCE_MARGIN = 0.1


@pytest.fixture
def manager():
    return DigitalPerfectDrone("test_drone")


@pytest.mark.asyncio
async def test_connection_logic(manager: DigitalPerfectDrone):
    assert await manager.get_type() == "Digital Simulated"
    assert manager._drone is None

    assert await manager.connect()
    assert manager._drone is not None
    assert await manager.get_type() == "Digital Drone"
    assert await manager.is_connected()

    await manager.disconnect()
    assert manager._drone is None


@pytest.mark.asyncio
async def test_takeoff(manager: DigitalPerfectDrone):
    DEFAULT_TAKEOFF_ALT = 10.0
    await manager.connect()
    assert await manager.take_off() == common_protocol.ResponseStatus.COMPLETED
    assert manager._mode == anafi_perfect.FlightMode.LOITER
    assert manager._get_altitude_rel() - DEFAULT_TAKEOFF_ALT <= TOLERANCE_MARGIN
    assert manager._is_abs_altitude_reached(DEFAULT_TAKEOFF_ALT)
    await manager.disconnect()


@pytest.mark.asyncio
async def test_land(manager: DigitalPerfectDrone):
    await manager.connect()
    await manager.take_off()
    assert manager._is_hovering()
    assert await manager.land() == common_protocol.ResponseStatus.COMPLETED
    assert manager._is_landed()
    assert manager._mode == anafi_perfect.FlightMode.LOITER
    await manager.disconnect()


@pytest.mark.asyncio
async def test_hover(manager: DigitalPerfectDrone):
    await manager.connect()
    await manager.take_off()
    assert await manager.hover() == common_protocol.ResponseStatus.COMPLETED
    assert manager._is_hovering()
    assert manager._mode == anafi_perfect.FlightMode.LOITER
    curr_vel = manager._get_velocity_enu()
    assert np.allclose(
        [curr_vel["north"], curr_vel["east"], curr_vel["up"]],
        [0, 0, 0],
        rtol=1e-7,
        atol=1e-9,
    )
    await manager.disconnect()


@pytest.mark.asyncio
async def test_kill(manager: DigitalPerfectDrone):
    await manager.connect()
    assert await manager.kill() == common_protocol.ResponseStatus.NOTSUPPORTED


@pytest.mark.asyncio
async def test_update_home(manager: DigitalPerfectDrone):
    loc = common_protocol.Location
    loc.latitude = 10
    loc.longitude = 10
    loc.altitude = 0
    await manager.connect()
    assert await manager.set_home(loc) == common_protocol.ResponseStatus.COMPLETED
    assert manager._is_home_set(10, 10, 0)
    assert not manager._is_home_reached()


@pytest.mark.asyncio
async def test_set_global_position(manager: DigitalPerfectDrone):
    pass
