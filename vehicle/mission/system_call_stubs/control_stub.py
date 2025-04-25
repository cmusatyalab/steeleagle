import logging
from stub import Stub
import controlplane_pb2 as control_protocol
import common_pb2 as common_protocol

logger = logging.getLogger(__name__)

class ControlStub(Stub):

    def __init__(self):
        super().__init__(b'usr', 'hub.network.controlplane.mission_to_hub')

    def parse_response(self, response_parts):
        response = control_protocol.Response()
        response.ParseFromString(response_parts[0])

        stub_response = self.request_map.get(response.seq_num)
        if not stub_response:
            logger.error(f"Unknown seq_num: {response.seq_num}")
            return

        if response.resp in (common_protocol.ResponseStatus.OK, common_protocol.ResponseStatus.COMPLETED):
            stub_response.grant_permission()
            stub_response.put_result(response)
        else:
            logger.error(f"Drone response status: {response.resp}")

        stub_response.set()

    async def run(self):
        await self.receiver_loop(self.parse_response)
   
    ''' Vehicle methods '''
    async def take_off(self):
        logger.info("take_off")
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleAction.TAKEOFF
        result = await self.send_and_wait(request)
        return result.resp if result else False

    async def land(self):
        logger.info("land")
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleAction.LAND
        result = await self.send_and_wait(request)
        return result.resp if result else False

    async def rth(self):
        logger.info("rth")
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleAction.RTH
        result = await self.send_and_wait(request)
        return result.resp if result else False
    
    async def hover(self):
        logger.info("hover")
        request = control_protocol.Request()
        request.veh.action = control_protocol.VehicleAction.HOVER
        result = await self.send_and_wait(request)
        return result.resp if result else False

    async def set_velocity(self, forward_vel, right_vel, up_vel, angle_vel):
        logger.info("set_velocity")
        request = control_protocol.Request()
        request.veh.velocity_body.forward_vel = forward_vel
        request.veh.velocity_body.right_vel = right_vel
        request.veh.velocity_body.up_vel = up_vel
        request.veh.velocity_body.angle_vel = angle_vel
        result = await self.send_and_wait(request)
        return result.resp if result else False
    
    async def set_relative_position(self, forward, right, up, angle):
        pass
    
    
    async def set_gps_location(self, latitude, longitude, altitude, bearing):
        logger.info("set_gps_location")
        request = control_protocol.Request()
        request.veh.location.latitude = latitude
        request.veh.location.longitude = longitude
        request.veh.location.absolute_altitude = altitude
        request.veh.location.heading = bearing
        result = await self.send_and_wait(request)
        return result.resp if result else False
    
    async def switchCamera(self, camera_id):
        pass
    
    '''Compute methods'''
    async def clear_compute_result(self, compute_key):
        logger.info("Clearing results")
        cpt_req = control_protocol.Request()
        cpt_req.cpt.key = compute_key
        cpt_req.cpt.action = control_protocol.ComputeAction.CLEAR
        await self.send_and_wait(cpt_req)