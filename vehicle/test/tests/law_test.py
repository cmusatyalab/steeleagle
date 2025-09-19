import pytest
import asyncio
from enum import Enum
import logging
# Helper import
from test.helpers import send_requests, Request
# Protocol import
import steeleagle_sdk.protocol.common_pb2 as common_proto
import steeleagle_sdk.protocol.services.control_service_pb2 as control_proto
import steeleagle_sdk.protocol.services.mission_service_pb2 as mission_proto
# Sequencer import
from test.message_sequencer import Topic

logger = logging.getLogger(__name__)

class Test_Law:
    '''
    Test class focused on vehicle control laws and their effects.
    '''
    @pytest.mark.order(1)
    @pytest.mark.asyncio
    async def test_allowed_commands(self, messages, swarm_controller, mission, kernel):
        # Start test:
        requests = [
            # This command should be blocked because we do not have control authority
            Request('Control.Arm', control_proto.ArmRequest(), 9, 'internal'),
            Request('Control.Arm', control_proto.ArmRequest(), 2, 'server'),
            Request('Mission.Start', mission_proto.StartRequest(), 2, 'server'),
            Request('Control.Disarm', control_proto.DisarmRequest(), 2, 'internal'),
            Request('Mission.Stop', mission_proto.StopRequest(), 2, 'server'),
            # This command should be blocked because we do not have control authority
            Request('Control.Arm', control_proto.ArmRequest(), 9, 'internal')
        ]
    
        output = await send_requests(requests, swarm_controller, mission) 
        assert(messages == output)

    @pytest.mark.order(2)
    @pytest.mark.asyncio
    async def test_payload_matcher(self, messages, swarm_controller, mission, kernel):
        # Start test:
        requests = [
            # This command should transit us to LOCAL mode
            Request('Mission.Start', mission_proto.StartRequest(), 2, 'server'),
            # This command should transit us to REMOTE mode
            Request('Control.TakeOff', control_proto.TakeOffRequest(take_off_altitude=10.0), 2, 'internal'),
            # Which should deny this request...
            Request('Control.Land', control_proto.LandRequest(), 9, 'internal'),
            # This command should transit us to LOCAL mode
            Request('Mission.Start', mission_proto.StartRequest(), 2, 'server'),
            Request('Control.Land', control_proto.LandRequest(), 2, 'internal'),
            Request('Control.TakeOff', control_proto.TakeOffRequest(take_off_altitude=5.0), 2, 'internal'),
            # This command should not be denied, and transit us to REMOTE mode
            Request('Control.SetGlobalPosition', control_proto.SetGlobalPositionRequest(location=common_proto.Location(latitude=10.0)), 2, 'internal'),
            # This should be denied
            Request('Control.Land', control_proto.LandRequest(), 9, 'internal'),
            # This should not
            Request('Control.Land', control_proto.LandRequest(), 2, 'server')
        ]

        output = await send_requests(requests, swarm_controller, mission) 
        assert(messages == output)
