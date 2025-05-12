
import ast
import json
import logging
from system_call_stubs.stub import Stub
import controlplane_pb2 as control_protocol
import common_pb2 as common_protocol

logger = logging.getLogger(__name__)

class ReportStub(Stub):

    def __init__(self, user_path):
        self.waypoint_path = user_path + '/way_points_map.json'
        logger.info(f"ReportStub: waypoint_path: {self.waypoint_path=}")
        super().__init__(b'usr', 'hub.network.controlplane.mission_to_hub_2')

    def parse_control_response(self, response_parts):
        self.parse_response(response_parts, control_protocol.Request)

    async def run(self):
        await self.receiver_loop(self.parse_control_response)

    ''' Mission methods '''
    async def send_notification(self, msg):
        
        self.coordinates_res = {
            'status': None,
            'patrol_areas': [],
            'altitude': None
        }
        
        logger.info(f"Sending notification: {msg=}")
        report = control_protocol.Response()
        if (msg == 'start'):
            report.resp = common_protocol.ResponseStatus.OK
        elif (msg == 'finish'):
            report.resp = common_protocol.ResponseStatus.COMPLETED
        logger.info(f"Send notification: waiting for send_and_wait: {report=}")
        update = await self.send_and_wait(report)
        logger.info(f"recv update: {update=}")
        
        
        for patrol_area in update.msn.patrol_area.areas:
            logger.info(f"Patrol area: {patrol_area=}")
            self.coordinates_res['patrol_areas'].append(patrol_area)
        
        self.coordinates_res['status'] = update.msn.patrol_area.status
        self.coordinates_res['altitude'] = update.msn.patrol_area.altitude
        
        return self.coordinates_res

    async def get_waypoints(self, area):
        # Read the waypoints from the waypoint path
        with open(self.waypoint_path, 'r') as f:
            waypoints = f.read()

        waypoints_map = json.loads(waypoints)
        logger.info(f"waypoints_map: {waypoints_map=}")
        waypoints_val = waypoints_map.get(area)
        logger.info(f"waypoints_val: {waypoints_val=}")
        return waypoints_val