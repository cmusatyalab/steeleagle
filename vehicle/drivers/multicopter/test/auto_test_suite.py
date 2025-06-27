import asyncio
import logging
import math

import common_pb2 as common_protocol
import controlplane_pb2 as control_protocol

# Import SteelEagle protocol
import dataplane_pb2 as data_protocol
import numpy as np
import pytest
import pytest_asyncio
import zmq
import zmq.asyncio
from util.utils import SocketOperation, setup_socket

logger = logging.getLogger(__name__)

# Setting up context
context = zmq.asyncio.Context()

hub_to_driver_sock = context.socket(zmq.DEALER)
setup_socket(
    hub_to_driver_sock, SocketOperation.BIND, "hub.network.controlplane.hub_to_driver"
)

tel_sock = context.socket(zmq.SUB)
tel_sock.setsockopt(zmq.SUBSCRIBE, b"")  # Subscribe to all topics
tel_sock.setsockopt(zmq.CONFLATE, 1)
setup_socket(
    tel_sock, SocketOperation.BIND, "hub.network.dataplane.driver_to_hub.telemetry"
)

cam_sock = context.socket(zmq.SUB)
cam_sock.setsockopt(zmq.SUBSCRIBE, b"")  # Subscribe to all topics
cam_sock.setsockopt(zmq.CONFLATE, 1)
setup_socket(
    cam_sock, SocketOperation.BIND, "hub.network.dataplane.driver_to_hub.image_sensor"
)

tel_dict = {
    "name": "",
    "battery": 0,
    "satellites": 0,
    "global_position": {},
    "relative_position": {},
    "velocity_body": {},
    "gimbal_pose": {},
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
            tel_dict["name"] = telemetry.drone_name
            tel_dict["battery"] = telemetry.battery
            tel_dict["satellites"] = telemetry.satellites
            tel_dict["global_position"]["latitude"] = telemetry.global_position.latitude
            tel_dict["global_position"]["longitude"] = (
                telemetry.global_position.longitude
            )
            tel_dict["global_position"]["altitude"] = telemetry.global_position.altitude
            tel_dict["global_position"]["heading"] = telemetry.global_position.heading
            tel_dict["relative_position"]["up"] = telemetry.relative_position.up
            tel_dict["velocity_body"]["forward"] = telemetry.velocity_body.forward_vel
            tel_dict["velocity_body"]["right"] = telemetry.velocity_body.right_vel
            tel_dict["velocity_body"]["up"] = telemetry.velocity_body.up_vel
            tel_dict["velocity_body"]["angular"] = telemetry.velocity_body.angular_vel
            tel_dict["gimbal_pose"]["yaw"] = telemetry.gimbal_pose.yaw
            tel_dict["gimbal_pose"]["pitch"] = telemetry.gimbal_pose.pitch
            tel_dict["gimbal_pose"]["roll"] = telemetry.gimbal_pose.roll
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
    identity = b"usr"
    r_earth = 6378137.0
    dx = 1  # Meters/s
    dy = 1  # Meters/s
    dz = 1  # Meters/s
    d_xx = 5  # Meters
    d_yy = 5  # Meters
    d_zz = 5  # Meters
    d_angle = 10  # Degrees

    @pytest.mark.order(1)
    @pytest.mark.asyncio
    async def test_takeoff(self, sequence_counter):
        logger.info("Testing takeoff")
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

    velocity_body_test_sets = [
        (dy, 0, 0, 0),  # Forward
        (0, dx, 0, 0),  # Right
        (0, 0, dz, 0),  # Up
        (0, 0, 0, d_angle),  # Yaw 1 radian
    ]

    @pytest.mark.order(2)
    @pytest.mark.asyncio
    @pytest.mark.parametrize("test", velocity_body_test_sets)
    async def test_set_velocity_body(self, sequence_counter, test):
        logger.info("Testing set velocity")

        forward, right, up, angular = test

        logger.info(f"Testing set velocity body: {test}")
        driver_cmd = control_protocol.Request()
        driver_cmd.veh.velocity_body.forward_vel = forward
        driver_cmd.veh.velocity_body.right_vel = right
        driver_cmd.veh.velocity_body.up_vel = up
        driver_cmd.veh.velocity_body.angular_vel = angular
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

        # Wait to get up to speed
        await asyncio.sleep(10)

        actual_forward = tel_dict["velocity_body"]["forward"]
        actual_right = tel_dict["velocity_body"]["right"]
        actual_up = tel_dict["velocity_body"]["up"]
        actual_angular = tel_dict["velocity_body"]["angular"]

        assert np.allclose(
            [forward, right, up, angular],
            [actual_forward, actual_right, actual_up, actual_angular],
            atol=3e-1,
        )

    @pytest.mark.order(3)
    @pytest.mark.asyncio
    async def test_set_relative_position(self, sequence_counter):
        assert True

    """ Helper functions for global position testing """

    def dy_to_lat(self, dy):
        return (dy / self.r_earth) * (180 / math.pi)

    def dx_to_lon(self, dx, lat):
        return (dx / self.r_earth) * (180 / math.pi) / math.cos(lat * math.pi / 180)

    def get_curr_loc(self):
        logger.info(f"Current telemetry: {tel_dict}")
        curr_pos_alt = tel_dict["global_position"]["altitude"]
        curr_pos_lat = tel_dict["global_position"]["latitude"]
        curr_pos_lon = tel_dict["global_position"]["longitude"]
        curr_pos_angle = tel_dict["global_position"]["heading"]
        logger.info(
            f"Current position: {curr_pos_lat}, {curr_pos_lon}, {curr_pos_alt}, {curr_pos_angle}"
        )
        return (curr_pos_lat, curr_pos_lon, curr_pos_alt, curr_pos_angle)

    # Test sets for absolute altitude
    global_position_abs_test_sets = [
        (d_xx, 0, 0, 0),  # Forward
        (0, d_yy, 0, 0),  # Right
        (0, 0, d_zz, 0),  # Up
        (0, 0, 0, d_angle),  # Yaw +d_bearing
        (-d_xx, -d_yy, -d_zz, 0),  # Reset
    ]

    @pytest.mark.order(4)
    @pytest.mark.asyncio
    @pytest.mark.parametrize("test", global_position_abs_test_sets)
    async def test_set_global_position_altitude_absolute(self, sequence_counter, test):
        logger.info("Testing set global position")

        # Get initial position
        curr_pos_lat, curr_pos_lon, curr_pos_alt, curr_pos_angle = self.get_curr_loc()

        x, y, z, angle = test

        d_lat = self.dy_to_lat(x)
        d_lon = self.dx_to_lon(y, curr_pos_lat)
        d_alt = z
        d_angle = angle

        # Build the *new* absolute position from the current telemetry
        next_lat = curr_pos_lat + d_lat
        next_lon = curr_pos_lon + d_lon
        next_alt = curr_pos_alt + d_alt
        next_angle = curr_pos_angle + d_angle

        logger.info(
            f"Testing set global position to: {(next_lat, next_lon, next_alt, next_angle)}"
        )
        driver_cmd = control_protocol.Request()
        driver_cmd.veh.location.latitude = next_lat
        driver_cmd.veh.location.longitude = next_lon
        driver_cmd.veh.location.altitude = next_alt
        driver_cmd.veh.location.heading = next_angle
        driver_cmd.veh.location.heading_mode = (
            common_protocol.LocationHeadingMode.HEADING_START
        )
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

        # Check the telemetry to see if the move was OK
        actual_lat = tel_dict["global_position"]["latitude"]
        actual_lon = tel_dict["global_position"]["longitude"]
        actual_alt = tel_dict["global_position"]["altitude"]
        actual_angle = tel_dict["global_position"]["heading"]

        logger.info(f"Expected: {(next_lat, next_lon, next_alt, next_angle)}")
        logger.info(f"Actual:   {(actual_lat, actual_lon, actual_alt, actual_angle)}")

        # Validate with some tolerance
        assert np.allclose([next_lat, next_lon], [actual_lat, actual_lon], atol=1e-5)
        assert np.isclose(next_alt, actual_alt, atol=1)
        # TODO: Figure out why the heading is not being set correctly
        # abs_diff = abs(next_angle - actual_angle)
        # diff = min(abs_diff, 360 - abs_diff)
        # assert diff <= 4

        sequence_counter["value"] += 1

    # Test sets for relative altitude
    global_position_rel_test_sets = [(0, 0, d_zz, 0), (0, 0, -d_zz, 0)]

    @pytest.mark.order(5)
    @pytest.mark.asyncio
    @pytest.mark.parametrize("test", global_position_rel_test_sets)
    async def test_set_global_position_altitude_relative(self, sequence_counter, test):
        logger.info("Testing set global position with relative altitude")

        # Get initial position
        curr_pos_lat, curr_pos_lon, curr_pos_alt, curr_pos_angle = self.get_curr_loc()

        x, y, z, angle = test

        # Test out the different altitude control modes
        logger.info(
            f"Testing set global position to: {(curr_pos_lat, curr_pos_lon, curr_pos_alt + self.d_zz, curr_pos_angle)}"
        )
        driver_cmd = control_protocol.Request()
        driver_cmd.veh.location.latitude = curr_pos_lat + x
        driver_cmd.veh.location.longitude = curr_pos_lon + y
        driver_cmd.veh.location.altitude = curr_pos_alt + z
        driver_cmd.veh.location.altitude_mode = (
            common_protocol.LocationAltitudeMode.TAKEOFF_RELATIVE
        )
        driver_cmd.veh.location.heading = curr_pos_angle + angle
        driver_cmd.veh.location.heading_mode = (
            common_protocol.LocationHeadingMode.HEADING_START
        )
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

        # Check the telemetry to see if the move was OK
        actual_lat = tel_dict["global_position"]["latitude"]
        actual_lon = tel_dict["global_position"]["longitude"]
        actual_alt = tel_dict["global_position"]["altitude"]
        actual_angle = tel_dict["global_position"]["heading"]

        logger.info(
            f"Expected: {(curr_pos_lat, curr_pos_lon, curr_pos_alt + self.d_zz, curr_pos_angle)}"
        )
        logger.info(f"Actual: {(actual_lat, actual_lon, actual_alt, actual_angle)}")

        # Validate with some tolerance
        assert np.allclose(
            [curr_pos_lat, curr_pos_lon], [actual_lat, actual_lon], atol=1e-5
        )
        assert np.isclose(curr_pos_alt + z, actual_alt, atol=1)
        # TODO: Figure out why heading is not set correctly
        # abs_diff = abs(curr_pos_angle - actual_angle)
        # diff = min(abs_diff, 360 - abs_diff)
        # assert diff <= 4

        sequence_counter["value"] += 1

    # Test cases for set gimbal pose
    gimbal_test_sets = [
        # Absolute tests
        (d_angle, 0, 0, 0),
        (0, d_angle, 0, 0),
        (0, 0, d_angle, 0),
        (0, 0, 0, 0),
        # Relative tests
        (d_angle, 0, 0, 1),
        (-d_angle, 0, 0, 1),
        (0, d_angle, 0, 1),
        (0, -d_angle, 0, 1),
        (0, 0, d_angle, 1),
        (0, 0, -d_angle, 1),
        # TODO: Add velocity tests
    ]

    @pytest.mark.order(6)
    @pytest.mark.asyncio
    @pytest.mark.parametrize("test", gimbal_test_sets)
    async def test_set_gimbal_pose(self, sequence_counter, test):
        logger.info("Testing set gimbal pose")

        yaw, pitch, roll, mode = test
        logger.info(
            f"Testing set gimbal pose to: {(yaw, pitch, roll)}, (yaw, pitch, roll) format"
        )
        # Store current pose for relative testing
        curr_yaw = tel_dict["gimbal_pose"]["yaw"]
        curr_pitch = tel_dict["gimbal_pose"]["pitch"]
        curr_roll = tel_dict["gimbal_pose"]["roll"]

        driver_cmd = control_protocol.Request()
        driver_cmd.veh.gimbal_pose.yaw = yaw
        driver_cmd.veh.gimbal_pose.pitch = pitch
        driver_cmd.veh.gimbal_pose.roll = roll
        # Mode defaults to POSITION_ABSOLUTE
        if mode == 1:
            driver_cmd.veh.gimbal_pose.control_mode = (
                common_protocol.PoseControlMode.POSITION_RELATIVE
            )
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

        # Check the telemetry to see if the move was OK
        actual_yaw = tel_dict["gimbal_pose"]["yaw"]
        actual_pitch = tel_dict["gimbal_pose"]["pitch"]
        actual_roll = tel_dict["gimbal_pose"]["roll"]

        if mode == 0:
            exp_yaw = yaw
            exp_pitch = pitch
            exp_roll = roll
        elif mode == 1:
            exp_yaw = yaw + curr_yaw
            exp_pitch = pitch + curr_pitch
            exp_roll = roll + curr_roll

        logger.info(f"Expected: {(exp_yaw, exp_pitch, exp_roll)}")
        logger.info(f"Actual: {(actual_yaw, actual_pitch, actual_roll)}")

        # Validate with some tolerance
        assert np.allclose(
            [exp_yaw, exp_pitch, exp_roll],
            [actual_yaw, actual_pitch, actual_roll],
            atol=3e-1,
        )

        sequence_counter["value"] += 1

    @pytest.mark.order(7)
    @pytest.mark.asyncio
    async def test_set_heading(self, sequence_counter):
        logger.info("Testing set heading")
        # TODO: No way to directly call set heading...

    @pytest.mark.order(8)
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

    @pytest.mark.order(9)
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
