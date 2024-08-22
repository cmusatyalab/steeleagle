import pytest
import asyncio
import json
from syncer import sync
from parrotdrone import ParrotDrone

@pytest.fixture(scope='session')
def drone():
    kwargs = {'sim': True}
    drone = ParrotDrone(**kwargs)
    sync(drone.connect())
    yield drone
    sync(drone.disconnect())

@pytest.mark.asyncio
async def test_isConnected(drone):
    assert drone.isConnected() == True

@pytest.mark.asyncio
async def test_takeOff(drone):
    await drone.takeOff()
    await asyncio.sleep(3)
    assert await drone.getAltitudeRel() >= 0

@pytest.mark.asyncio
async def test_setAttitude(drone):
    pitch = 10.0
    await drone.setAttitude(pitch, 0.0, 0.0, None)
    await asyncio.sleep(3)
    att = await drone.getAttitude()
    assert abs(att["pitch"] - pitch) < 1 
    await drone.hover()
    await asyncio.sleep(3)
    
    roll = 10.0
    await drone.setAttitude(0.0, roll, 0.0, None)
    await asyncio.sleep(3)
    att = await drone.getAttitude()
    assert abs(att["roll"] - roll) < 1 
    await drone.hover()
    await asyncio.sleep(3)
    
    theta = 10.0
    await drone.setAttitude(0.0, 0.0, 0.0, theta)
    await asyncio.sleep(3)
    att = await drone.getAttitude()
    assert abs(att["yaw"] - theta) < 1 
    await drone.hover()
    await asyncio.sleep(3)

@pytest.mark.asyncio
async def test_setVelocity(drone):
    forward = 2.0
    await drone.setVelocity(forward, 0.0, 0.0, 0.0)
    await asyncio.sleep(3)
    vel = await drone.getVelocityBody()
    assert abs(vel["forward"] - forward) < 1 
    await drone.hover()
    await asyncio.sleep(3)
    
    right = 2.0
    await drone.setVelocity(0.0, right, 0.0, 0.0)
    await asyncio.sleep(3)
    vel = await drone.getVelocityBody()
    assert abs(vel["right"] - right) < 1 
    await drone.hover()
    await asyncio.sleep(3)
    
    up = 2.0
    await drone.setVelocity(0.0, 0.0, up, 0.0)
    await asyncio.sleep(3)
    vel = await drone.getVelocityBody()
    assert abs(vel["up"] - up) < 1 
    await drone.hover()
    await asyncio.sleep(3)
