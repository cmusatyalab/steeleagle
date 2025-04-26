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

    def parse_response(self, response_parts):
        response = data_protocol.Response()
        response.ParseFromString(response_parts[0])

        stub_response = self.request_map.get(response.seq_num)
        if not stub_response:
            logger.error(f"Unknown seq_num: {response.seq_num}")
            return

        if response.resp == common_protocol.ResponseStatus.COMPLETED:
            stub_response.put_result(response)
        else:
            logger.error("Compute response failed")

        stub_response.set()

    async def run(self):
        await self.receiver_loop(self.parse_response)
    
    
    ''' compute methods '''
    # Get results for a compute engine
    async def get_compute_result(self, compute_key):
        logger.info(f"Getting results for compute type: {compute_key}")
        cpt_req = data_protocol.Request()
        cpt_req.cpt.result_key = compute_key
        result = await self.send_and_wait(cpt_req)
        return result


    ''' Telemetry methods '''
    async def get_telemetry(self):
        logger.info("Getting telemetry")
        request = data_protocol.Request(tel=data_protocol.TelemetryRequest())
        logger.info(f"Requesting telemetry: {request}")
        rep = await self.send_and_wait(request)
        result = rep.tel
        telDict = {
            "name": None,
            "battery": None,
            "satellites": None,
            "gps": {"latitude": None, "longitude": None, "altitude": None},
            "velocity_body": {"forward": None, "right": None, "up": None},
        }
        if result:
            logger.debug(f"Got telemetry: {result}\n")
            telDict["name"] = result.drone_name
            telDict["battery"] = result.battery
            telDict["satellites"] = result.satellites
            telDict["gps"]["latitude"] = result.global_position.latitude
            telDict["gps"]["longitude"] = result.global_position.longitude
            telDict["gps"]["altitude"] = result.global_position.absolute_altitude
            telDict["velocity_body"]["forward"] = result.velocity_body.forward_vel
            telDict["velocity_body"]["right"] = result.velocity_body.right_vel
            telDict["velocity_body"]["up"] = result.velocity_body.up_vel
            telDict["heading"] = result.global_position.heading
            logger.debug(f"finished receiving Telemetry: {telDict}")
            return telDict
        else:
            logger.error("Failed to get telemetry")    
            return None