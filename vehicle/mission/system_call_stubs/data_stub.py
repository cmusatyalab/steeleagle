# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import logging
from system_call_stubs.stub import Stub
import dataplane_pb2 as data_protocol

logger = logging.getLogger(__name__)

class DataStub(Stub):
    def __init__(self):
        super().__init__(b'usr', 'hub.network.dataplane.mission_to_hub', 'data')

    def parse_data_response(self, response_parts):
        self.parse_response(response_parts, data_protocol.Response)

    async def run(self):
        await self.receiver_loop(self.parse_data_response)

    ''' Compute methods '''
    # Get results for a compute engine
    async def get_compute_result(self, compute_type):
        cpt_req = data_protocol.Request()
        cpt_req.cpt.type = compute_type
        rep = await self.send_and_wait(cpt_req)

        if rep is None:
            logger.error(f"Failed to get compute result: No response received for {compute_type=}")
            return None

        result_list = []
        for result in rep.cpt.result:
            result_list.append(result.generic_result)

        logger.debug(f"get_compute_result: {compute_type=}, {result_list=}")
        return result_list

    ''' Telemetry methods '''
    async def get_telemetry(self):
        try:
            request = data_protocol.Request(tel=data_protocol.TelemetryRequest())
            rep = await self.send_and_wait(request)

            if rep is None:
                logger.error("Failed to get telemetry: No response received")
                return None

            result = rep.tel
            tel_dict = {
                "drone_name": None,
                "global_position": {"latitude": None, "longitude": None, "heading": None, \
                        "altitude": None, "relative_altitude": None},
                "relative_position": {"north": None, "east": None, "up": None},
                "velocity_enu": {"north": None, "east": None, "up": None},
                "velocity_body": {"forward": None, "right": None, "up": None},
                "gimbal_pose": {"yaw": None, "pitch": None, "roll": None},
                "home": {"latitude": None, "longitude": None, "altitude": None},
                "cameras": {},
                "alerts": {},
                "battery": None,
                "satellites": None,
                "status": None,
            }
            if result:
                # Name
                tel_dict["drone_name"] = result.drone_name
                # Global Position
                tel_dict["global_position"]["latitude"] = result.global_position.latitude
                tel_dict["global_position"]["longitude"] = result.global_position.longitude
                tel_dict["global_position"]["altitude"] = result.global_position.altitude
                tel_dict["global_position"]["relative_altitude"] = result.relative_position.up
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
                # Status
                tel_dict["status"] = result.status

                return tel_dict
            else:
                logger.error("Failed to get telemetry")
                return None
        except Exception as e:
            logger.error(e)

    async def update_current_task(self, current_task):
        logger.info("Updating current task")
        req = data_protocol.Request(task=data_protocol.UpdateCurrentTask(task_name=current_task))
        rep = await self.send_and_wait(req)
        logger.info(f"Got response {rep}")
        if rep is None:
            logger.error("Failed to send mission status")
