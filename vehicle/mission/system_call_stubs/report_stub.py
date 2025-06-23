import json
import logging
from system_call_stubs.stub import Stub
import controlplane_pb2 as control_protocol
import common_pb2 as common_protocol

logger = logging.getLogger(__name__)

class ReportStub(Stub):

    def __init__(self, user_path):
        self.waypoint_path = user_path + '/waypoint.json'
        logger.info(f"ReportStub: waypoint_path: {self.waypoint_path=}")
        super().__init__(b'usr', 'hub.network.controlplane.mission_to_hub_2', 'report')

    def parse_control_response(self, response_parts):
        self.parse_response(response_parts, control_protocol.Request)

    async def run(self):
        await self.receiver_loop(self.parse_control_response)

    ''' Mission methods '''
    async def send_notification(self, msg):
        logger.info(f"Sending notification: {msg=}")
        report = control_protocol.Response()
        if (msg == 'start'):
            report.resp = common_protocol.ResponseStatus.OK
        elif (msg == 'finish'):
            report.resp = common_protocol.ResponseStatus.COMPLETED
        
        update = await self.send_and_wait(report)
        
        if update is None:
            logger.error("Failed to send notification: No response received")
            return None
        
        update_res = {
            'status': None,
            'patrol_areas': [],
            'altitude': None
        }
        if update.msn.patrol_area.status == common_protocol.PatrolStatus.CONTINUE:
            update_res['status'] = "running"
            update_res['altitude'] = update.msn.patrol_area.altitude
            for patrol_area in update.msn.patrol_area.areas:
                update_res['patrol_areas'].append(patrol_area)
        else :
            update_res['status'] = "finished"

        return update_res
    
    async def get_waypoints(self, area_path):
        try:
            logger.info(f"get_waypoints: {self.waypoint_path=}")
            with open(self.waypoint_path, 'r') as f:
                waypoints = f.read()

            waypoints_map = json.loads(waypoints)
            keys = area_path.split('.')
            coords = waypoints_map
            for key in keys:
                coords = coords.get(key)
                if coords is None:
                    logger.warning(f"Key '{key}' not found in waypoints map.")
                    return None

            formatted_coords = [{'lng': lng, 'lat': lat} for lng, lat in coords]
            return formatted_coords

        except Exception as e:
            logger.error(f"Error reading waypoints: {e}")
            return None