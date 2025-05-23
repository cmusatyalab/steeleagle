import asyncio
import logging
import zmq
import zmq.asyncio
from util.utils import setup_socket, SocketOperation
import pytest_asyncio
import pytest
import numpy as np
import math
# Import SteelEagle protocol
import dataplane_pb2 as data_protocol
import controlplane_pb2 as control_protocol
import common_pb2 as common_protocol

logger = logging.getLogger(__name__)

# Setting up conetxt
context = zmq.asyncio.Context()

hub_to_driver_sock = context.socket(zmq.DEALER)
setup_socket(hub_to_driver_sock, SocketOperation.BIND, 'hub.network.controlplane.hub_to_driver')

tel_sock = context.socket(zmq.SUB)
tel_sock.setsockopt(zmq.SUBSCRIBE, b'') # Subscribe to all topics
tel_sock.setsockopt(zmq.CONFLATE, 1)
setup_socket(tel_sock, SocketOperation.BIND, 'hub.network.dataplane.driver_to_hub.telemetry')

cam_sock = context.socket(zmq.SUB)
cam_sock.setsockopt(zmq.SUBSCRIBE, b'')  # Subscribe to all topics
cam_sock.setsockopt(zmq.CONFLATE, 1)
setup_socket(cam_sock, SocketOperation.BIND, 'hub.network.dataplane.driver_to_hub.image_sensor')

tel_dict = {
    "name": "",
    "battery": 0,
    "satellites": 0,
    "gps": {},
    "imu": {},
}

# Background telemetry receiver
async def recv_telemetry():
    logger.info("Entered recv_telemetry()")
    loop = asyncio.get_running_loop()
    logger.info(f"recv_telemetry is running on event loop: {loop} (id={id(loop)})")
    while True:
        try:
            msg = await tel_sock.recv()
            telemetry = data_protocol.Telemetry()
            telemetry.ParseFromString(msg)
            tel_dict['name'] = telemetry.drone_name
            tel_dict['battery'] = telemetry.battery
            tel_dict['satellites'] = telemetry.satellites
            tel_dict['gps']['latitude'] = telemetry.global_position.latitude
            tel_dict['gps']['longitude'] = telemetry.global_position.longitude
            tel_dict['gps']['altitude'] = telemetry.global_position.absolute_altitude
            tel_dict["gps"]['heading'] = telemetry.global_position.heading
            tel_dict['imu']['forward'] = telemetry.velocity_body.forward_vel
            tel_dict['imu']['right'] = telemetry.velocity_body.right_vel
            tel_dict['imu']['up'] = telemetry.velocity_body.up_vel
            logger.debug(f"Received telemetry message: {telemetry}")
            await asyncio.sleep(0.3)  # Small delay to avoid hogging CPU
        except Exception as e:
            logger.error(f"Telemetry handler error: {e}")


@pytest_asyncio.fixture(scope="function", autouse=True)
async def start_telemetry_listener():
    logger.info("Starting telemetry listener task")
    telemetry_task = asyncio.create_task(recv_telemetry())
    await asyncio.sleep(1)  # Give some time for the task to start
    yield
    logger.info("cancelling telemetry listener task")
    telemetry_task.cancel()
    try:
        await telemetry_task
    except asyncio.CancelledError:
        logger.info("Telemetry listener task cancelled")
        
@pytest.fixture(scope="class")
def sequence_counter():
    return {"value": 0}

class TestSuiteClass:
    identity = b'usr'
    r_earth = 6378137.0
    dx = 1 # Meters/s
    dy = 1 # Meters/s
    dz = 1 # Meters/s
    d_xx = 5 # Meters
    d_yy = 5 # Meters
    d_zz = 5 # Meters
    d_angle = 10 # Degrees
    
    @pytest.mark.order(1)
    @pytest.mark.asyncio
    async def test_takeoff(self, sequence_counter):
        logger.info("Testing takeoff")
        loop = asyncio.get_running_loop()
        logger.info(f"test_takeoff is running on event loop: {loop} (id={id(loop)})")
        driver_cmd = control_protocol.Request()
        driver_cmd.veh.action = control_protocol.VehicleAction.TAKEOFF
        driver_cmd.seq_num = sequence_counter["value"]
        message = driver_cmd.SerializeToString()
        await hub_to_driver_sock.send_multipart([self.identity, message])
 
        logger.info("Waiting for response")       
        response = await hub_to_driver_sock.recv_multipart()
        driver_rep = control_protocol.Response()
        driver_rep.ParseFromString(response[1])
        seq_num = driver_rep.seq_num
        status = driver_rep.resp
        
        logger.info(f"Received response with seqNum: {seq_num}")
        assert seq_num == sequence_counter["value"]
        logger.info(f"Status: {status}")
        assert status == common_protocol.ResponseStatus.COMPLETED
        
        sequence_counter["value"] += 1
        
        await asyncio.sleep(5)
    
    @pytest.mark.order(2)
    @pytest.mark.asyncio
    async def test_set_get_velocity(self, sequence_counter):
        logger.info("Testing set velocity")
        loop = asyncio.get_running_loop()
        logger.info(f"test_set_get_velocity is running on event loop: {loop} (id={id(loop)})")
        test_sets = [
            (self.dy, 0, 0, 0), # Forward
            (0, self.dx, 0, 0), # Right
            (0, 0, self.dz, 0), # Up
            (0, 0, 0, self.d_angle), # Yaw 1 radian
        ]
        for test_set in test_sets:
            await asyncio.sleep(5)
            logger.info(f"Testing set velocity: {test_set}")
            driver_cmd = control_protocol.Request()
            driver_cmd.veh.velocity_body.forward_vel = test_set[0]
            driver_cmd.veh.velocity_body.right_vel = test_set[1]
            driver_cmd.veh.velocity_body.up_vel = test_set[2]
            driver_cmd.veh.velocity_body.angular_vel = test_set[3]
            driver_cmd.seq_num = sequence_counter["value"]
            message = driver_cmd.SerializeToString()
            await hub_to_driver_sock.send_multipart([self.identity, message])
            
            logger.info("Waiting for response")
            response = await hub_to_driver_sock.recv_multipart()
            driver_rep = control_protocol.Response()
            driver_rep.ParseFromString(response[1])
            seq_num = driver_rep.seq_num
            status = driver_rep.resp
            
            logger.info(f"Received response with seqNum: {seq_num}")
            assert seq_num == sequence_counter["value"]
            logger.info(f"Status: {status}")
            assert status == common_protocol.ResponseStatus.COMPLETED
            sequence_counter["value"] += 1  
    
    @pytest.mark.order(3)    
    @pytest.mark.asyncio
    async def test_set_get_rel_pos(self, sequence_counter):
        assert True
    
    
    def dy_to_lat(self, dy):
        return (dy / self.r_earth) * (180 / math.pi)
    
    def dx_to_lon(self, dx, lat ):
        return (dx / self.r_earth) * (180 / math.pi) / math.cos(lat* math.pi/180)
    
    def get_curr_loc(self):
        logger.info(f"Current telemetry: {tel_dict}")
        curr_pos_alt = tel_dict['gps']['altitude']
        curr_pos_lat = tel_dict['gps']['latitude']
        curr_pos_lon = tel_dict['gps']['longitude']
        curr_pos_angle = tel_dict['gps']['heading']
        logger.info(f"Current position: {curr_pos_lat}, {curr_pos_lon}, {curr_pos_alt}, {curr_pos_angle}")
        return (curr_pos_lat, curr_pos_lon, curr_pos_alt, curr_pos_angle)
    
    @pytest.mark.order(4)
    @pytest.mark.asyncio
    async def test_set_get_gps_pos(self, sequence_counter):
        logger.info("Testing set GPS position")

        # Get initial position
        curr_pos_lat, curr_pos_lon, curr_pos_alt, curr_pos_angle = self.get_curr_loc()

        test_sets = [
            (self.d_xx, 0, 0, 0),   # Forward
            (0, self.d_yy, 0, 0),   # Right
            (0, 0, self.d_zz, 0),   # Up
            (0, 0, 0, self.d_angle)  # Yaw +d_bearing
        ]

        for (x, y, z, angle) in test_sets:
            d_lat = self.dy_to_lat(x)
            d_lon = self.dx_to_lon(y, curr_pos_lat)
            d_alt = z
            d_angle = angle

            # Build the *new* absolute position from the current telemetry
            next_lat = curr_pos_lat + d_lat
            next_lon = curr_pos_lon + d_lon
            next_alt = curr_pos_alt + d_alt
            next_angle = curr_pos_angle + d_angle

            logger.info(f"Testing set GPS position to: {(next_lat, next_lon, next_alt, next_angle)}")
            driver_cmd = control_protocol.Request()
            driver_cmd.veh.location.latitude  = next_lat
            driver_cmd.veh.location.longitude = next_lon
            driver_cmd.veh.location.absolute_altitude  = next_alt
            driver_cmd.veh.location.heading = next_angle
            seq = sequence_counter["value"]
            logger.info(f"Sending command with seqNum: {seq}")
            driver_cmd.seq_num = sequence_counter["value"]
            message = driver_cmd.SerializeToString()
            await hub_to_driver_sock.send_multipart([self.identity, message])

            logger.info("Waiting for response")
            response = await hub_to_driver_sock.recv_multipart()
            driver_rep = control_protocol.Response()
            driver_rep.ParseFromString(response[1])
            seq_num = driver_rep.seq_num
            status = driver_rep.resp
            
            logger.info(f"Received response {driver_rep}")
            logger.info(f"Received response with seqNum: {seq_num}")
            assert seq_num == sequence_counter["value"]
            logger.info(f"Status: {status}")
            assert status == common_protocol.ResponseStatus.COMPLETED

            
            await asyncio.sleep(10)
            # Check the telemetry to see if the move was OK
            actual_lat = tel_dict["gps"]["latitude"]
            actual_lon = tel_dict["gps"]["longitude"]
            actual_alt = tel_dict["gps"]["altitude"]
            actual_angle = tel_dict["gps"]["heading"]

            logger.info(f"Expected: {(next_lat, next_lon, next_alt, next_angle)}")
            logger.info(f"Actual:   {(actual_lat, actual_lon, actual_alt, actual_angle)}")

            # Validate with some tolerance
            assert np.allclose([next_lat, next_lon], [actual_lat, actual_lon], atol=1e-5)
            assert np.isclose(next_alt, actual_alt, atol=1)
            abs_diff = abs(next_angle - actual_angle)
            diff = min(abs_diff, 360 - abs_diff)
            assert diff <= 4

            # Update curr psoition
            curr_pos_lat, curr_pos_lon, curr_pos_alt, curr_pos_angle = (
                actual_lat, actual_lon, actual_alt, actual_angle
            )
            
            sequence_counter["value"] += 1
        
    @pytest.mark.order(5)
    @pytest.mark.asyncio
    async def test_set_get_gimbal(self, sequence_counter):
        assert True
        
    @pytest.mark.order(6)
    @pytest.mark.asyncio
    async def test_set_get_bearing(self, sequence_counter):
        assert True

    @pytest.mark.order(7)        
    @pytest.mark.asyncio
    async def test_RTH(self, sequence_counter):
        logger.info("Testing return to home")
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleAction.RTH
        request.seq_num = sequence_counter["value"]
        message = request.SerializeToString()
        await hub_to_driver_sock.send_multipart([self.identity, message])
        
        logger.info("Waiting for response")
        response = await hub_to_driver_sock.recv_multipart()
        driver_rep = control_protocol.Response()
        driver_rep.ParseFromString(response[1])
        seq_num = driver_rep.seq_num  
        status = driver_rep.resp
        
        logger.info(f"Received response with seqNum: {seq_num}")
        assert seq_num == sequence_counter["value"]
        logger.info(f"Status: {driver_rep.resp}")
        assert status == common_protocol.ResponseStatus.COMPLETED
        sequence_counter["value"] += 1
        
    @pytest.mark.order(8)        
    @pytest.mark.asyncio
    async def test_land(self, sequence_counter):
        logger.info("Testing land")
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleAction.LAND
        request.seq_num = sequence_counter["value"]
        message = request.SerializeToString()
        await hub_to_driver_sock.send_multipart([self.identity, message])
        
        logger.info("Waiting for response")
        response = await hub_to_driver_sock.recv_multipart()
        driver_rep = control_protocol.Response()
        driver_rep.ParseFromString(response[1])
        seq_num = driver_rep.seq_num
        status = driver_rep.resp
        
        logger.info(f"Received response with seqNum: {seq_num}")
        assert seq_num == sequence_counter["value"]
        logger.info(f"Status: {status}")
        assert status == common_protocol.ResponseStatus.COMPLETED
        sequence_counter["value"] += 1
        
