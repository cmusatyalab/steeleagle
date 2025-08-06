import pytest
import pytest_asyncio
import asyncio
from enum import Enum
import time
import zmq
import zmq.asyncio
import grpc
from concurrent import futures
import subprocess
import logging
# Utility import
from util.sockets import setup_zmq_socket, SocketOperation
from util.rpc import generate_request, get_bind_addr
from util.config import query_config
from util.cleanup import register_cleanup_handler
# Protocol import
import python_bindings.common_pb2 as common_proto
import python_bindings.control_service_pb2 as control_proto
from python_bindings.control_service_pb2_grpc import add_ControlServicer_to_server
from python_bindings.report_service_pb2_grpc import add_ReportServicer_to_server
from python_bindings.mission_service_pb2_grpc import MissionStub
import python_bindings.testing_pb2 as test_proto
# Mock import
from message_sequencer import Topic, MessageSequencer
from mock_clients.mock_swarm_controller import MockSwarmController
from mock_services.mock_control_service import MockControlService

logger = logging.getLogger(__name__)

# Boilerplate setting up Swarm Controller
MESSAGES = []

# Register SIGKILL as an exception
register_cleanup_handler()

'''
Test fixture methods
'''
@pytest.fixture(scope='function')
def messages():
    yield MESSAGES
    MESSAGES.clear()

@pytest.fixture(scope='function')
def swarm_controller(messages):
    # Set up sc_socket to connect to the kernel
    sc_socket = zmq.asyncio.Context().socket(zmq.ROUTER)
    setup_zmq_socket(
        sc_socket,
        'cloudlet.swarm_controller.endpoint',
        SocketOperation.BIND
        )
    # Create the Swarm Controller and message sequencer
    sc_seq = MessageSequencer(
            Topic.SWARM_CONTROLLER,
            messages
            )
    sc = MockSwarmController(sc_socket, sc_seq)
    yield sc
    sc_socket.close()

@pytest.fixture(scope='function')
def background_services():
    # Set up test socket to coordinate testing
    test_socket = zmq.asyncio.Context().socket(zmq.ROUTER)
    setup_zmq_socket(
        test_socket,
        'internal.testing.endpoint',
        SocketOperation.BIND
        )
    # List of services to start in the background
    running = []
    subps = [
        ["python3", "start_mocks.py"],
        ["python3", "../kernel/control/manager.py"]
        ]

    for subp in subps:
        logger.info(f'Opening subprocess {subp[1]}...')
        s = subprocess.Popen(subp)
        logger.info(f'Subprocess running at PID: {s.pid}')
        running.append(s)
        time.sleep(1)
    yield test_socket
    for subp in running:
        logger.info(f'Closing subprocess {subp.pid}...')
        subp.terminate()
        subp.wait()

@pytest_asyncio.fixture(scope='function')
async def wait_for_services(background_services):
    # List of services required to run tests
    req_services = [
        test_proto.ServiceType.SC_HANDLER_SERVICE,
        test_proto.ServiceType.CONTROL_PROXY_SERVICE,
        test_proto.ServiceType.REPORT_SERVICE,
        test_proto.ServiceType.DRIVER_CONTROL_SERVICE
        ]
    # Wait for the necessary services to spin up
    start = time.time()
    timeout = 5.0
    while len(req_services) > 0 and time.time() - start < timeout:
        try:
            identity, ready = await background_services.recv_multipart(flags=zmq.NOBLOCK)
            logger.info(f'Service registered: {identity}')
            service = test_proto.ServiceReady()
            service.ParseFromString(ready)
            if service.readied_service in req_services:
                req_services.remove(service.readied_service)
        except zmq.error.Again:
            pass
        except (KeyboardInterrupt, asyncio.exceptions.CancelledError):
            return
    if len(req_services) > 0:
        raise TimeoutError(f"Service IDs {req_services} did not report in")

class Test_gRPC:
    '''
    Test class focused on stressing control flows through the vehicle.
    '''
    @pytest.mark.order(1)
    @pytest.mark.asyncio
    async def test_remote_control(self, swarm_controller, wait_for_services):
        # Start test:
        # Connect->Arm->TakeOff->SetVelocity->Land->Disarm->Disconnect
        requests = [
            control_proto.ConnectRequest(),
            control_proto.ArmRequest(),
            control_proto.TakeOffRequest(),
            control_proto.SetVelocityRequest(),
            control_proto.LandRequest(),
            control_proto.DisarmRequest(),
            control_proto.DisconnectRequest()
        ]
    
        output = []
        for req in requests:
            output.append((Topic.SWARM_CONTROLLER, req.DESCRIPTOR.name))
            output.append((Topic.DRIVER_CONTROL_SERVICE, req.DESCRIPTOR.name))
            for i in range(MockControlService.IN_PROGRESS_COUNT + 2):
                output.append((
                    Topic.SWARM_CONTROLLER,
                    req.DESCRIPTOR.name.replace("Request", "Response")
                    ))
    
        for req in requests:
            logger.info(f"Sending command: {req.DESCRIPTOR.name}") 
            await swarm_controller.send_recv_command(req)
        
        assert(MESSAGES == output)

    #@pytest.mark.order(2)
    #@pytest.mark.asyncio
    #async def test_mission_start(self):
    #    pass

    #@pytest.mark.order(3)
    #@pytest.mark.asyncio
    #async def test_mission_stop(self):
    #    pass

    #@pytest.mark.order(4)
    #@pytest.mark.asyncio
    #async def test_mission_rth(self):
    #    pass
    #
    #@pytest.mark.order(5)
    #@pytest.mark.asyncio
    #async def test_mission_report(self):
    #    pass
    #
    #@pytest.mark.order(6)
    #@pytest.mark.asyncio
    #async def test_mission_notify(self):
    #    pass
