# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import logging

import dataplane_pb2 as data_protocol
import google.protobuf.json_format as json_format

from system_call_stubs.stub import Stub

logger = logging.getLogger(__name__)


class DataStub(Stub):
    def __init__(self):
        super().__init__(b"usr", "hub.network.dataplane.mission_to_hub", "data")

    def parse_data_response(self, response_parts):
        self.parse_response(response_parts, data_protocol.Response)

    async def run(self):
        await self.receiver_loop(self.parse_data_response)

    """ Compute methods """

    # Get results for a compute engine
    async def get_compute_result(self, compute_type):
        cpt_req = data_protocol.Request()
        cpt_req.cpt.type = compute_type
        rep = await self.send_and_wait(cpt_req)

        if rep is None:
            logger.error(
                f"Failed to get compute result: No response received for {compute_type=}"
            )
            return None

        result_list = []
        for result in rep.cpt.result:
            result_list.append(result.generic_result)

        logger.debug(f"get_compute_result: {compute_type=}, {result_list=}")
        return result_list

    """ Telemetry methods """

    async def get_telemetry(self):
        try:
            request = data_protocol.Request(tel=data_protocol.TelemetryRequest())
            rep = await self.send_and_wait(request)

            if rep is None:
                logger.error("Failed to get telemetry: No response received")
                return None

            result = rep.tel

            if not result:
                logger.error("Failed to get telemetry")
                return None

            tel_dict = json_format.MessageToDict(
                rep.tel,
                always_print_fields_with_no_presence=True,
                preserving_proto_field_name=True,
            )

            tel_dict["data_age_ms"] = rep.data_age_ms

            return tel_dict

        except Exception as e:
            logger.error(e)

    async def update_current_task(self, current_task):
        logger.info("Updating current task")
        req = data_protocol.Request(
            task=data_protocol.UpdateCurrentTask(task_name=current_task)
        )
        rep = await self.send_and_wait(req)
        logger.info(f"Got response {rep}")
        if rep is None:
            logger.error("Failed to send mission status")
