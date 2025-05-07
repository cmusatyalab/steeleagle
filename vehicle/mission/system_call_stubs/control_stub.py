import ast
import json
import logging
from system_call_stubs.stub import Stub
import controlplane_pb2 as control_protocol
import common_pb2 as common_protocol

logger = logging.getLogger(__name__)

class ControlStub(Stub):

    def __init__(self, waypoint_path):
        self.waypoint_path = waypoint_path
        super().__init__(b'usr', 'hub.network.controlplane.mission_to_hub')

    def parse_control_response(self, response_parts):
        self.parse_response(response_parts, control_protocol.Response)

    async def run(self):
        await self.receiver_loop(self.parse_control_response)

    ''' Vehicle methods '''
    async def take_off(self):
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleAction.TAKEOFF
        result = await self.send_and_wait(request)
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def land(self):
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleAction.LAND
        result = await self.send_and_wait(request)
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def rth(self):
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleAction.RTH
        result = await self.send_and_wait(request)
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def hover(self):
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleAction.HOVER
        result = await self.send_and_wait(request)
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def set_gps_location(self, latitude, longitude, altitude, bearing):
        request = control_protocol.Request()
        request.veh.location.latitude = latitude
        request.veh.location.longitude = longitude
        request.veh.location.absolute_altitude = altitude
        request.veh.location.heading = bearing
        result = await self.send_and_wait(request)
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def set_relative_position_enu(self, north, east, up, angle):
        request = control_protocol.Request()
        request.veh.position_enu.north = north
        request.veh.position_enu.east = east
        request.veh.position_enu.up = up
        request.veh.position_enu.angle = angle
        result = await self.send_and_wait(request)
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def set_relative_position_body(self, forward, right, up, angle):
        request = control_protocol.Request()
        request.veh.position_body.forward = forward
        request.veh.position_body.right = right
        request.veh.position_body.up = up
        request.veh.position_body.angle = angle
        result = await self.send_and_wait(request)
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def set_velocity_enu(self, north_vel, east_vel, up_vel, angle_vel):
        request = control_protocol.Request()
        request.veh.velocity_enu.north_vel = north_vel
        request.veh.velocity_enu.east_vel = east_vel
        request.veh.velocity_enu.up_vel = up_vel
        request.veh.velocity_enu.angle_vel = angle_vel
        result = await self.send_and_wait(request)
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def set_velocity_body(self, forward_vel, right_vel, up_vel, angle_vel):
        request = control_protocol.Request()
        request.veh.velocity_body.forward_vel = forward_vel
        request.veh.velocity_body.right_vel = right_vel
        request.veh.velocity_body.up_vel = up_vel
        request.veh.velocity_body.angular_vel = angle_vel
        result = await self.send_and_wait(request)
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    ''' Compute methods '''
    async def clear_compute_result(self, compute_type):
        cpt_req = control_protocol.Request()
        cpt_req.cpt.type = compute_type
        cpt_req.cpt.action = control_protocol.ComputeAction.CLEAR_COMPUTE
        result = await self.send_and_wait(cpt_req)
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False

    async def configure_compute(self, compute_model, hsv_lower_bound, hsv_upper_bound):
        try:
            logger.info(f"Starting configure_compute")
            cpt_req = control_protocol.Request()
            cpt_req.cpt.lower_bound.h = hsv_lower_bound[0]
            cpt_req.cpt.lower_bound.s = hsv_lower_bound[1]
            cpt_req.cpt.lower_bound.v = hsv_lower_bound[2]
            cpt_req.cpt.upper_bound.h = hsv_upper_bound[0]
            cpt_req.cpt.upper_bound.s = hsv_upper_bound[1]
            cpt_req.cpt.upper_bound.v = hsv_upper_bound[2]
            cpt_req.cpt.model = compute_model
            cpt_req.cpt.action = control_protocol.ComputeAction.CONFIGURE_COMPUTE
            logger.info("Await for send_and_wait")
            result = await self.send_and_wait(cpt_req)
            logger.info("Done awaiting for send_and_wait")
            return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False
        except Exception as e:
            logger.info(f"{e}")

    ''' Mission methods '''
    async def send_notification(self, msg):
        request = control_protocol.Request()
        request.veh.action = control_protocol.MissionAction.NOTIFICATION
        request.msn.notification = msg
        result = await self.send_and_wait(request)
        return result.msn_notification

    async def get_waypoints(self, tag):
        # Read the waypoints from the waypoint path
        with open(self.waypoint_path, 'r') as f:
            waypoints = f.read()

        waypoints_map = json.loads(waypoints)
        waypoints_val = waypoints_map.get(tag)
        return waypoints_val
