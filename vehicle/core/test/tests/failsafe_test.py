import pytest
import asyncio
from enum import Enum
import logging
# Helper import
from helpers import send_requests, Request
# Protocol import
import steeleagle_sdk.protocol.services.control_service_pb2 as control_proto
import steeleagle_sdk.protocol.services.mission_service_pb2 as mission_proto
# Sequencer import
from message_sequencer import Topic

logger = logging.getLogger(__name__)

class Test_Failsafe:
    '''
    Test class focused on testing disconnect failsafes.
    '''
    @pytest.mark.order(1)
    @pytest.mark.asyncio
    async def test_server_disconnect_failsafe(self, messages, swarm_controller, mission, core):
        # Start test:
        requests = [
            Request('Control.Arm', control_proto.ArmRequest(), control_proto.ArmResponse(), 2, 'server'),
            Request('Control.Disarm', control_proto.DisarmRequest(), control_proto.DisarmResponse(), 2, 'server')
            # If we wait after sending this, it should trigger a failsafe!
        ]

        output = await send_requests(requests, swarm_controller, mission)
        logger.info('Waiting 5 seconds for failsafe trigger DC_SERVER!')
        await asyncio.sleep(2)
        # We should have seen a failsafe trigger!
        assert(messages != output)
        output.append((Topic.DRIVER_CONTROL_SERVICE, 'HoldRequest'))
        assert(messages == output)
