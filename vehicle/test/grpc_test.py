import pytest
import pytest_asyncio
import asyncio
from enum import Enum
import zmq
import zmq.asyncio
import grpc
from concurrent import futures
import logging
# Utility import
from util.sockets import setup_zmq_socket, SocketOperation
from util.rpc import generate_request
from util.config import query_config
# Protocol import
import python_bindings.common_pb2 as common_proto
import python_bindings.driver_service_pb2 as driver_proto
from python_bindings.driver_service_pb2_grpc import add_DriverServicer_to_server
from python_bindings.report_service_pb2_grpc import add_ReportServicer_to_server
from python_bindings.mission_service_pb2_grpc import MissionStub
# Mock imports
from message_sequencer import Topic, MessageSequencer
from mock_clients.mock_swarm_controller import MockSwarmController
from mock_services.mock_driver_service import MockDriverService

logger = logging.getLogger(__name__)

class Test_gRPC:
    '''
    Test class focused on stressing control flows through the vehicle.
    '''
    @pytest.mark.order(1)
    @pytest.mark.asyncio
    async def test_remote_control(self):
        # Boilerplate setting up Swarm Controller and Driver
        messages = []
        
        socket = zmq.asyncio.Context().socket(zmq.ROUTER)
        endpoint = query_config('cloudlet.swarm_controller.endpoint')
        port = endpoint.split(':')[-1]
        addr = f"0.0.0.0:{port}"
        setup_zmq_socket(
            socket,
            addr,
            SocketOperation.BIND,
            is_url=True
            )
        sc_seq = MessageSequencer(
                Topic.SWARM_CONTROLLER,
                messages
                )
        sc = MockSwarmController(socket, sc_seq)

        host_addr = query_config(
                'internal.control_service.endpoint'
                ).split(':')[-1]
        host_url = f'[::]:{host_addr}'
        server = grpc.aio.server(
                futures.ThreadPoolExecutor(max_workers=10),
                )
        driver_seq = MessageSequencer(
                Topic.DRIVER_SERVICE,
                messages
                )
        add_DriverServicer_to_server(MockDriverService(driver_seq), server)
        server.add_insecure_port(host_url)

        # Start test:
        # Connect->Arm->TakeOff->SetVelocity->Land->Disarm->Disconnect
        requests = [
            driver_proto.ConnectRequest(),
            driver_proto.ArmRequest(),
            driver_proto.TakeOffRequest(),
            driver_proto.SetVelocityRequest(),
            driver_proto.LandRequest(),
            driver_proto.DisarmRequest(),
            driver_proto.DisconnectRequest()
        ]

        output = []
        for req in requests:
            output.append((Topic.SWARM_CONTROLLER, req.DESCRIPTOR.name))
            output.append((Topic.DRIVER_SERVICE, req.DESCRIPTOR.name))
            for i in range(MockDriverService.IN_PROGRESS_COUNT + 2):
                output.append((
                    Topic.SWARM_CONTROLLER,
                    req.DESCRIPTOR.name.replace("Request", "Response")
                    ))

        for req in requests:
            logger.info(f"Sending command: {req.DESCRIPTOR.name}") 
            await sc.send_recv_command(req)
        
        assert(messages == output)

    @pytest.mark.order(2)
    @pytest.mark.asyncio
    async def test_mission_start(self):
        pass

    @pytest.mark.order(3)
    @pytest.mark.asyncio
    async def test_mission_stop(self):
        pass

    @pytest.mark.order(4)
    @pytest.mark.asyncio
    async def test_mission_rth(self):
        pass
    
    @pytest.mark.order(5)
    @pytest.mark.asyncio
    async def test_mission_report(self):
        pass
    
    @pytest.mark.order(6)
    @pytest.mark.asyncio
    async def test_mission_notify(self):
        pass
