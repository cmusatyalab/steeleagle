import asyncio
import logging
import time
import zmq
import zmq.asyncio
import asyncio
from collections import defaultdict
from util.utils import setup_socket, SocketOperation
import cnc_protocol.cnc_pb2 as cnc_pb2
import pytest


logger = logging.getLogger(__name__)

# Setting up conetxt
context = zmq.asyncio.Context()

cmd_back_sock = context.socket(zmq.DEALER)
setup_socket(cmd_back_sock, SocketOperation.BIND, 'CMD_BACK_PORT', 'Created command backend socket endpoint')

tel_sock = context.socket(zmq.SUB)
tel_sock.setsockopt(zmq.SUBSCRIBE, b'') # Subscribe to all topics
tel_sock.setsockopt(zmq.CONFLATE, 1)
setup_socket(tel_sock, SocketOperation.BIND, 'TEL_PORT', 'Created telemetry socket endpoint')

cam_sock = context.socket(zmq.SUB)
cam_sock.setsockopt(zmq.SUBSCRIBE, b'')  # Subscribe to all topics
cam_sock.setsockopt(zmq.CONFLATE, 1)
setup_socket(cam_sock, SocketOperation.BIND, 'CAM_PORT', 'Created camera socket endpoint')



# Background telemetry receiver
async def recv_telemetry():
    while True:
        try:
            msg = await tel_sock.recv()
            telemetry = cnc_pb2.Telemetry()
            telemetry.ParseFromString(msg)
            logger.debug(f"Received telemetry message: {telemetry}")
            await asyncio.sleep(0.3)  # Small delay to avoid hogging CPU
        except Exception as e:
            logger.error(f"Telemetry handler error: {e}")


@pytest.fixture(scope="session", autouse=True)
async def start_telemetry_listener():
    logger.info("Starting telemetry listener task")
    telemetry_task = asyncio.create_task(recv_telemetry())
    yield
    telemetry_task.cancel()
    try:
        await telemetry_task
    except asyncio.CancelledError:
        logger.info("Telemetry listener task cancelled")

class TestSuiteClass:
    command_seq = 0
    
    @pytest.mark.asyncio
    async def test_takeoff():
        assert True

    @pytest.mark.asyncio
    async def test_set_get_velocity():
        assert True
        
    @pytest.mark.asyncio
    async def test_set_get_rel_pos():
        assert True
        
    @pytest.mark.asyncio
    async def test_set_get_gps_pos():
        assert True
        
    @pytest.mark.asyncio
    async def test_set_get_gimbal():
        assert True
        
    @pytest.mark.asyncio
    async def test_set_get_bearing():
        assert True
        
    @pytest.mark.asyncio
    async def test_RTH():
        assert True
        
    @pytest.mark.asyncio
    async def test_land():
        assert True