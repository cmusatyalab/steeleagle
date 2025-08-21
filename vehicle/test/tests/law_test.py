import pytest
import asyncio
from enum import Enum
import logging
# Helper import
from helpers import send_requests, Request
# Protocol import
import python_bindings.common_pb2 as common_proto
import python_bindings.control_service_pb2 as control_proto
import python_bindings.mission_service_pb2 as mission_proto
# Sequencer import
from message_sequencer import Topic

logger = logging.getLogger(__name__)

class Test_Law:
    '''
    Test class focused on law through the vehicle.
    '''
    @pytest.mark.order(1)
    @pytest.mark.asyncio
    async def test_allowed_commands(self, messages, swarm_controller, mission, background_services):
        # Start test:
        requests = [
            # This command should be blocked because we do not have control authority
            Request('Control.Arm', control_proto.ArmRequest(), control_proto.ArmResponse(), 9, 'internal'),
            Request('Control.Arm', control_proto.ArmRequest(), control_proto.ArmResponse(), 2, 'server'),
            Request('Mission.Start', mission_proto.StartRequest(), mission_proto.StartResponse(), 2, 'server'),
            Request('Control.Disarm', control_proto.DisarmRequest(), control_proto.DisarmResponse(), 2, 'internal'),
            Request('Mission.Stop', mission_proto.StopRequest(), mission_proto.StopResponse(), 2, 'server'),
            # This command should be blocked because we do not have control authority
            Request('Control.Arm', control_proto.ArmRequest(), control_proto.ArmResponse(), 9, 'internal')
        ]
    
        output = await send_requests(requests, swarm_controller, mission) 
        assert(messages == output)

    # TODO: test_payload_matcher
    @pytest.mark.order(1)
    @pytest.mark.asyncio
    async def test_payload_matcher(self, messages, swarm_controller, mission, background_services):
        # Start test:
        requests = [
            # This command should transit us to LOCAL mode
            Request('Mission.Start', mission_proto.StartRequest(), mission_proto.StartResponse(), 2, 'server'),
            # This command should transit us to REMOTE mode
            Request('Control.TakeOff', control_proto.TakeOffRequest(take_off_altitude=10.0), control_proto.TakeOffResponse(), 2, 'internal'),
            # Which should deny this request...
            Request('Control.Land', control_proto.LandRequest(), control_proto.LandResponse(), 9, 'internal'),
            # This command should transit us to LOCAL mode
            Request('Mission.Start', mission_proto.StartRequest(), mission_proto.StartResponse(), 2, 'server'),
            Request('Control.Land', control_proto.LandRequest(), control_proto.LandResponse(), 2, 'internal'),
            Request('Control.TakeOff', control_proto.TakeOffRequest(take_off_altitude=5.0), control_proto.TakeOffResponse(), 2, 'internal'),
            # This command should not be denied, and transit us to REMOTE mode
            Request('Control.SetGlobalPosition', control_proto.SetGlobalPositionRequest(location=common_proto.Location(latitude=10.0)), control_proto.SetGlobalPositionResponse(), 2, 'internal'),
            # This should be denied
            Request('Control.Land', control_proto.LandRequest(), control_proto.LandResponse(), 9, 'internal'),
            # This should not
            Request('Control.Land', control_proto.LandRequest(), control_proto.LandResponse(), 2, 'server')
        ]

        output = await send_requests(requests, swarm_controller, mission) 
        assert(messages == output)
