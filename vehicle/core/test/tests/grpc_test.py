import pytest
import asyncio
from enum import Enum
import logging
# Helper import
from helpers import send_requests, Request
# Protocol import
import steeleagle_sdk.protocol.services.control_service_pb2 as control_proto
import steeleagle_sdk.protocol.services.mission_service_pb2 as mission_proto
import steeleagle_sdk.protocol.services.report_service_pb2 as report_proto
# Sequencer import
from message_sequencer import Topic

logger = logging.getLogger(__name__)

class Test_gRPC:
    '''
    Test class focused on stressing control flows through the vehicle.
    '''
    @pytest.mark.order(1)
    @pytest.mark.asyncio
    async def test_command(self, messages, swarm_controller, mission, core):
        # Start test:
        requests = [
            Request('Control.Arm', control_proto.ArmRequest(), control_proto.ArmResponse()),
            Request('Control.TakeOff', control_proto.TakeOffRequest(), control_proto.TakeOffResponse()),
            Request('Control.Land', control_proto.LandRequest(), control_proto.LandResponse()),
            Request('Control.Disarm', control_proto.DisarmRequest(), control_proto.DisarmResponse())
        ]
    
        output = await send_requests(requests, swarm_controller, mission) 
        assert(messages == output)

    @pytest.mark.order(2)
    @pytest.mark.asyncio
    async def test_mission_control(self, messages, swarm_controller, mission, core):
        # Start test:
        requests = [
            Request('Mission.Start', mission_proto.StartRequest(), mission_proto.StartResponse(), 2, 'server'),
            Request('Control.Arm', control_proto.ArmRequest(), control_proto.ArmResponse(), 2, 'internal'),
            Request('Control.TakeOff', control_proto.TakeOffRequest(), control_proto.TakeOffResponse(), 2, 'internal'),
            Request('Control.Land', control_proto.LandRequest(), control_proto.LandResponse(), 2, 'internal'),
            Request('Control.Disarm', control_proto.DisarmRequest(), control_proto.DisarmResponse(), 2, 'internal'),
            Request('Mission.Stop', mission_proto.StopRequest(), mission_proto.StopResponse(), 2, 'server')
        ]

        output = await send_requests(requests, swarm_controller, mission) 
        assert(messages == output)

    @pytest.mark.order(3)
    @pytest.mark.asyncio
    async def test_mission_notify(self, messages, swarm_controller, mission, core):
        # Start test:
        requests = [
            Request('Mission.Notify', mission_proto.NotifyRequest(), mission_proto.NotifyResponse())
        ]
        
        output = await send_requests(requests, swarm_controller, mission) 
        assert(messages == output)

    @pytest.mark.order(4)
    @pytest.mark.asyncio
    async def test_mission_report(self, messages, swarm_controller, mission, core):
        # Start test:
        requests = [
            Request('Mission.Start', mission_proto.StartRequest(), mission_proto.StartResponse(), 2, 'server'),
            Request('Report.SendReport', report_proto.SendReportRequest(), report_proto.SendReportResponse(), 2, 'internal'),
            Request('Mission.Stop', mission_proto.StopRequest(), mission_proto.StopResponse(), 2, 'server')
        ]

        output = await send_requests(requests, swarm_controller, mission)
        assert(messages == output)
