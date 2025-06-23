import logging

import common_pb2 as common_protocol
import controlplane_pb2 as control_protocol

from system_call_stubs.stub import Stub

logger = logging.getLogger(__name__)

class ControlStub(Stub):

    def __init__(self):
        super().__init__(b'usr', 'hub.network.controlplane.mission_to_hub', 'control')

    def parse_control_response(self, response_parts):
        self.parse_response(response_parts, control_protocol.Response)

    async def run(self):
        await self.receiver_loop(self.parse_control_response)

    ''' Vehicle methods '''
    async def take_off(self):
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleAction.TAKEOFF
        result = await self.send_and_wait(request)
        if result is None:
            logger.error("Takeoff failed: No response received")
            return False
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def land(self):
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleAction.LAND
        result = await self.send_and_wait(request)
        if result is None:
            logger.error("Landing failed: No response received")
            return False
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def rth(self):
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleAction.RTH
        result = await self.send_and_wait(request)
        if result is None:
            logger.error("RTH failed: No response received")
            return False
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def hover(self):
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleAction.HOVER
        result = await self.send_and_wait(request)
        if result is None:
            logger.error("Hover failed: No response received")
            return False
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def set_gps_location(self, latitude, longitude, altitude, bearing=0, altitude_mode='RELATIVE', heading_mode='TO_TARGET', velocity=(0, 0, 0)):
        request = control_protocol.Request()
        request.veh.location.latitude = latitude
        request.veh.location.longitude = longitude
        request.veh.location.altitude = altitude
        request.veh.location.heading = bearing
        if altitude_mode == 'ABSOLUTE':
            request.veh.location.altitude_mode = \
                common_protocol.LocationAltitudeMode.ABSOLUTE
        elif altitude_mode == 'RELATIVE':
            request.veh.location.altitude_mode = \
                common_protocol.LocationAltitudeMode.TAKEOFF_RELATIVE
        else:
            logger.error("Invalid altitude mode")
            return False
        if heading_mode == 'TO_TARGET':
            request.veh.location.heading_mode = \
                common_protocol.LocationHeadingMode.TO_TARGET
        elif heading_mode == 'HEADING_START':
            request.veh.location.heading_mode = \
                common_protocol.LocationHeadingMode.HEADING_START
        else:
            logger.error("Invalid heading mode")
            return False
        request.veh.location.max_velocity.north_vel = velocity[0]
        request.veh.location.max_velocity.east_vel = velocity[0]
        request.veh.location.max_velocity.up_vel = velocity[1]
        request.veh.location.max_velocity.angular_vel = velocity[2]
        result = await self.send_and_wait(request)
        if result is None:
            logger.error("Setting GPS location failed: No response received")
            return False
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def set_relative_position_enu(self, north, east, up, angle):
        request = control_protocol.Request()
        request.veh.position_enu.north = north
        request.veh.position_enu.east = east
        request.veh.position_enu.up = up
        request.veh.position_enu.angle = angle
        result = await self.send_and_wait(request)
        if result is None:
            logger.error("Setting relative position ENU failed: No response received")
            return False
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def set_relative_position_body(self, forward, right, up, angle):
        request = control_protocol.Request()
        request.veh.position_body.forward = forward
        request.veh.position_body.right = right
        request.veh.position_body.up = up
        request.veh.position_body.angle = angle
        result = await self.send_and_wait(request)
        if result is None:
            logger.error("Setting relative position body failed: No response received")
            return False
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def set_velocity_enu(self, north_vel, east_vel, up_vel, angle_vel):
        request = control_protocol.Request()
        request.veh.velocity_enu.north_vel = north_vel
        request.veh.velocity_enu.east_vel = east_vel
        request.veh.velocity_enu.up_vel = up_vel
        request.veh.velocity_enu.angle_vel = angle_vel
        result = await self.send_and_wait(request)
        if result is None:
            logger.error("Setting velocity ENU failed: No response received")
            return False
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def set_velocity_body(self, forward_vel, right_vel, up_vel, angle_vel):
        request = control_protocol.Request()
        request.veh.velocity_body.forward_vel = forward_vel
        request.veh.velocity_body.right_vel = right_vel
        request.veh.velocity_body.up_vel = up_vel
        request.veh.velocity_body.angular_vel = angle_vel
        result = await self.send_and_wait(request)
        if result is None:
            logger.error("Setting velocity body failed: No response received")
            return False
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def set_gimbal_pose(self, pitch, roll, yaw, mode='ABSOLUTE'):
        request = control_protocol.Request()
        request.veh.gimbal_pose.pitch = pitch
        request.veh.gimbal_pose.roll = roll
        request.veh.gimbal_pose.yaw = yaw
        if mode == 'ABSOLUTE':
            request.veh.gimbal_pose.control_mode = \
                common_protocol.PoseControlMode.POSITION_ABSOLUTE
        elif mode == 'RELATIVE':
            request.veh.gimbal_pose.control_mode = \
                common_protocol.PoseControlMode.POSITION_RELATIVE
        else:
            request.veh.gimbal_pose.control_mode = \
                common_protocol.PoseControlMode.VELOCITY

        result = await self.send_and_wait(request)
        if result is None:
            logger.error("Setting gimbal pose failed: No response received")
            return False
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    ''' Compute methods '''
    async def clear_compute_result(self, compute_type):
        logger.info("clearing compute result")
        cpt_req = control_protocol.Request()
        cpt_req.cpt.type = compute_type
        cpt_req.cpt.action = control_protocol.ComputeAction.CLEAR_COMPUTE
        result = await self.send_and_wait(cpt_req)
        if result is None:
            logger.error("Clearing compute result failed: No response received")
            return False
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def configure_compute(self, compute_model, hsv_lower_bound, hsv_upper_bound):
        try:
            logger.info(f"configuring compute model: {compute_model}, lower bound: {hsv_lower_bound}, upper bound: {hsv_upper_bound}")
            cpt_req = control_protocol.Request()
            cpt_req.cpt.lower_bound.h = hsv_lower_bound[0]
            cpt_req.cpt.lower_bound.s = hsv_lower_bound[1]
            cpt_req.cpt.lower_bound.v = hsv_lower_bound[2]
            cpt_req.cpt.upper_bound.h = hsv_upper_bound[0]
            cpt_req.cpt.upper_bound.s = hsv_upper_bound[1]
            cpt_req.cpt.upper_bound.v = hsv_upper_bound[2]
            cpt_req.cpt.model = compute_model
            cpt_req.cpt.action = control_protocol.ComputeAction.CONFIGURE_COMPUTE
            result = await self.send_and_wait(cpt_req)
            if result is None:
                logger.error("Configure compute failed: No response received")
                return False
            return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False
        except Exception as e:
            logger.info(f"{e}")
