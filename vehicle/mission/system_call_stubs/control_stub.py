import logging
from system_call_stubs.stub import Stub
import controlplane_pb2 as control_protocol
import common_pb2 as common_protocol

logger = logging.getLogger(__name__)

class ControlStub(Stub):

    def __init__(self):
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

    async def set_velocity(self, forward_vel, right_vel, up_vel, angle_vel):
        request = control_protocol.Request()
        request.veh.velocity_body.forward_vel = forward_vel
        request.veh.velocity_body.right_vel = right_vel
        request.veh.velocity_body.up_vel = up_vel
        request.veh.velocity_body.angle_vel = angle_vel
        result = await self.send_and_wait(request)
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False
    
    async def set_relative_position(self, forward, right, up, angle):
        pass
    
    async def set_gps_location(self, latitude, longitude, altitude, bearing):
        request = control_protocol.Request()
        request.veh.location.latitude = latitude
        request.veh.location.longitude = longitude
        request.veh.location.absolute_altitude = altitude
        request.veh.location.heading = bearing
        result = await self.send_and_wait(request)
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False
    
    '''Compute methods'''
    async def clear_compute_result(self, compute_key):
        cpt_req = control_protocol.Request()
        cpt_req.cpt.key = compute_key
        cpt_req.cpt.action = control_protocol.ComputeAction.CLEAR
        result = await self.send_and_wait(cpt_req)
        return True if result.resp == common_protocol.ResponseStatus.COMPLETED else False
