import pytest
import asyncio
from enum import Enum
import logging
# Helper import
from test.helpers import send_requests, Request
# Protocol import
import steeleagle_sdk.protocol.services.control_service_pb2 as control_proto
import steeleagle_sdk.protocol.services.mission_service_pb2 as mission_proto
import steeleagle_sdk.protocol.services.report_service_pb2 as report_proto
# Sequencer import
from test.message_sequencer import Topic

logger = logging.getLogger(__name__)

class Test_gRPC:
    '''
    Test class focused on stressing control flows through the vehicle.
    '''
    @pytest.mark.order(1)
    @pytest.mark.asyncio
    async def test_command(self, messages, swarm_controller, mission, kernel):
        # Start test:
        requests = [
            Request('Control.Arm', control_proto.ArmRequest()),
            Request('Control.TakeOff', control_proto.TakeOffRequest()),
            Request('Control.Land', control_proto.LandRequest()),
            Request('Control.Disarm', control_proto.DisarmRequest())
        ]
    
        output = await send_requests(requests, swarm_controller, mission) 
        assert(messages == output)

    @pytest.mark.order(2)
    @pytest.mark.asyncio
    async def test_mission_control(self, messages, swarm_controller, mission, kernel):
        # Start test:
        requests = [
            Request('Mission.Start', mission_proto.StartRequest(), 2, 'server'),
            Request('Control.Arm', control_proto.ArmRequest(), 2, 'internal'),
            Request('Control.TakeOff', control_proto.TakeOffRequest(), 2, 'internal'),
            Request('Control.Land', control_proto.LandRequest(), 2, 'internal'),
            Request('Control.Disarm', control_proto.DisarmRequest(), 2, 'internal'),
            Request('Mission.Stop', mission_proto.StopRequest(), 2, 'server')
        ]

        output = await send_requests(requests, swarm_controller, mission) 
        assert(messages == output)

    @pytest.mark.order(3)
    @pytest.mark.asyncio
    async def test_mission_notify(self, messages, swarm_controller, mission, kernel):
        # Start test:
        requests = [
            Request('Mission.Notify', mission_proto.NotifyRequest())
        ]
        
        output = await send_requests(requests, swarm_controller, mission) 
        assert(messages == output)

    @pytest.mark.order(4)
    @pytest.mark.asyncio
    async def test_mission_report(self, messages, swarm_controller, mission, kernel):
        # Start test:
        requests = [
            Request('Mission.Start', mission_proto.StartRequest(), 2, 'server'),
            Request('Report.SendReport', report_proto.SendReportRequest(), 2, 'internal'),
            Request('Mission.Stop', mission_proto.StopRequest(), 2, 'server')
        ]

        output = await send_requests(requests, swarm_controller, mission)
        assert(messages == output)
