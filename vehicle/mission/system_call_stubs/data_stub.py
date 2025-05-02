# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import logging
from system_call_stubs.stub import Stub
import dataplane_pb2 as data_protocol
import common_pb2 as common_protocol

logger = logging.getLogger(__name__)
        
class DataStub(Stub):
    def __init__(self):
        super().__init__(b'usr', 'hub.network.dataplane.mission_to_hub')

    def parse_data_response(self, response_parts):
        self.parse_response(response_parts, data_protocol.Response)

    async def run(self):
        await self.receiver_loop(self.parse_data_response)
    
    ''' Compute methods '''
    # Get results for a compute engine
    async def get_compute_result(self, compute_type):
        cpt_req = data_protocol.Request()
        cpt_req.cpt.type = compute_type
        result = await self.send_and_wait(cpt_req)
        return result

    ''' Telemetry methods '''
    async def get_telemetry(self):
        request = data_protocol.Request(tel=data_protocol.TelemetryRequest())
        rep = await self.send_and_wait(request)
        result = rep.tel
        tel_dict = {
            "drone_name": None,
            "global_position": {"latitude": None, "longitude": None, "heading": None, \
                    "altitude": None, "relative_altitude": None},
            "relative_position": {"north": None, "east": None, "up": None},
            "velocity_enu": {"north": None, "east": None, "up": None},
            "velocity_body": {"forward": None, "right": None, "up": None},
            "gimbal_pose": {"yaw": None, "pitch": None, "roll": None}
            "home": {"latitude": None, "longitude": None, "altitude": None},
            "cameras": {},
            "alerts": {},
            "battery": None,
            "satellites": None
        }
        if result:
            # Name
            tel_dict["name"] = result.drone_name
            # Global Position
            tel_dict["global_position"]["latitude"] = result.global_position.latitude
            tel_dict["global_position"]["longitude"] = result.global_position.longitude
            tel_dict["global_position"]["altitude"] = result.global_position.absolute_altitude
            tel_dict["global_position"]["relative_altitude"] = result.global_position.relative_altitude
            tel_dict["global_position"]["heading"] = result.global_position.heading
            # Velocity Body
            tel_dict["velocity_body"]["forward"] = result.velocity_body.forward_vel
            tel_dict["velocity_body"]["right"] = result.velocity_body.right_vel
            tel_dict["velocity_body"]["up"] = result.velocity_body.up_vel
            # Gimbal
            tel_dict["gimbal_pose"]["yaw"] = result.gimbal_pose.yaw
            tel_dict["gimbal_pose"]["pitch"] = result.gimbal_pose.pitch
            tel_dict["gimbal_pose"]["roll"] = result.gimbal_pose.roll
            # Battery & Satellites
            tel_dict["battery"] = result.battery
            tel_dict["satellites"] = result.satellites
            # TODO: Status
            return tel_dict
        else:
            logger.error("Failed to get telemetry")    
            return None
