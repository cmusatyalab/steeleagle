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
from dataclasses import dataclass
from typing import Any
# Utility import
from util.sockets import setup_zmq_socket, SocketOperation
from util.rpc import generate_request
from util.config import query_config
from util.cleanup import register_cleanup_handler
# Protocol import
import python_bindings.common_pb2 as common_proto
import python_bindings.control_service_pb2 as control_proto
import python_bindings.mission_service_pb2 as mission_proto
import python_bindings.testing_pb2 as test_proto
# Mock import
from message_sequencer import Topic, MessageSequencer
from mock_clients.mock_swarm_controller import MockSwarmController

logger = logging.getLogger(__name__)

# Test request holder
@dataclass
class Request:
    method_name: str = None
    request: Any = None
    response: Any = None
    status: int = 2
    identity: str = 'server'

# Register SIGKILL as an exception
register_cleanup_handler()

'''
Helper methods.
'''
async def wait_for_services(required, command_socket, timeout=5.0):
    # Wait for the necessary services to spin up
    start = time.time()
    while len(required) > 0 and time.time() - start < timeout:
        try:
            identity, ready = await command_socket.recv_multipart(flags=zmq.NOBLOCK)
            service = test_proto.ServiceReady()
            service.ParseFromString(ready)
            if service.readied_service in required:
                required.remove(service.readied_service)
        except zmq.error.Again:
            pass
        except (KeyboardInterrupt, asyncio.exceptions.CancelledError):
            return
    if len(required):
        raise TimeoutError(f"Services did not report in!")

async def send_requests(requests, swarm_controller, mission):
    # Send messages and read the output
    output = []
    output.append((Topic.DRIVER_CONTROL_SERVICE, 'ConnectRequest'))
    for req in requests:
        identity = req.identity
        if identity == 'internal':
            assert(await mission.send_recv_command(req))
            output.append((Topic.MISSION_SERVICE, req.request.DESCRIPTOR.name))
            service = req.method_name.split('.')[0]
            if service == 'Control' and req.status == 2:
                output.append((Topic.DRIVER_CONTROL_SERVICE, req.request.DESCRIPTOR.name))
            output.append((Topic.MISSION_SERVICE, req.request.DESCRIPTOR.name.replace('Request', 'Response')))
        elif identity == 'external' or identity == 'server':
            assert(await swarm_controller.send_recv_command(req))
            output.append((Topic.SWARM_CONTROLLER, req.request.DESCRIPTOR.name))
            service = req.method_name.split('.')[0]
            output.append((Topic.DRIVER_CONTROL_SERVICE if service == 'Control' else Topic.MISSION_SERVICE, req.request.DESCRIPTOR.name))
            output.append((Topic.SWARM_CONTROLLER, req.request.DESCRIPTOR.name.replace('Request', 'Response')))
    return output

'''
Test fixture methods.
'''
@pytest.fixture(scope='function')
def messages():
    messages = []
    yield messages

@pytest.fixture(scope='function')
def command_socket():
    # Set up command_socket to connect to the kernel
    command_socket = zmq.asyncio.Context().socket(zmq.ROUTER)
    setup_zmq_socket(
        command_socket,
        'cloudlet.swarm_controller.endpoint',
        SocketOperation.BIND
        )
    yield command_socket
    command_socket.close()

@pytest.fixture(scope='function')
def swarm_controller(messages, command_socket):
    # Create the Swarm Controller and message sequencer
    sc_seq = MessageSequencer(
            Topic.SWARM_CONTROLLER,
            messages
            )
    sc = MockSwarmController(command_socket, sc_seq)
    yield sc

@pytest_asyncio.fixture(scope='function')
async def mock_services(messages, command_socket):
    from serve_mock_services import serve_mock_services
    services = asyncio.create_task(serve_mock_services(messages))
    await asyncio.sleep(1)
    # Wait for needed services
    required = [
       test_proto.ServiceType.DRIVER_CONTROL_SERVICE,
       test_proto.ServiceType.MISSION_SERVICE
    ]
    await wait_for_services(required, command_socket)
    yield
    try:
        services.cancel()
        await services
    except asyncio.exceptions.CancelledError:
        pass

@pytest_asyncio.fixture(scope='function')
async def mission(messages):
    from mock_clients.mock_mission_client import MockMissionClient
    mission = MockMissionClient(messages)
    yield mission

@pytest_asyncio.fixture(scope='function')
async def background_services(mock_services, command_socket):
    # List of services to start in the background
    running = []
    subps = [
        ["python3", "../core/serve.py"]
        ]

    for subp in subps:
        logger.info(f'Opening subprocess {subp[1]}...')
        s = subprocess.Popen(subp)
        logger.info(f'Subprocess running at PID: {s.pid}')
        running.append(s)
        await asyncio.sleep(1)
    # Wait for needed services
    required = [
       test_proto.ServiceType.CORE_SERVICES
    ]
    await wait_for_services(required, command_socket)
    yield
    for subp in running:
        logger.info(f'Closing subprocess {subp.pid}...')
        subp.terminate()
        subp.wait()

class Test_gRPC:
    '''
    Test class focused on stressing control flows through the vehicle.
    '''
    @pytest.mark.order(1)
    @pytest.mark.asyncio
    async def test_remote_control(self, messages, swarm_controller, mission, background_services):
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
    async def test_mission_start(self, messages, swarm_controller, mission, background_services):
        # Start test:
        requests = [
            # This command should be blocked because we do not have control authority
            Request('Control.Arm', control_proto.ArmRequest(), control_proto.ArmResponse(), 9, 'internal'),
            Request('Mission.Start', mission_proto.StartRequest(), mission_proto.StartResponse(), 2, 'server'),
            Request('Control.Arm', control_proto.ArmRequest(), control_proto.ArmResponse(), 2, 'internal'),
            Request('Control.Disarm', control_proto.DisarmRequest(), control_proto.DisarmResponse(), 2, 'internal'),
            Request('Mission.Stop', mission_proto.StopRequest(), mission_proto.StopResponse(), 2, 'server'),
            # This command should be blocked because we do not have control authority
            Request('Control.Arm', control_proto.ArmRequest(), control_proto.ArmResponse(), 9, 'internal')
        ]
    
        output = await send_requests(requests, swarm_controller, mission) 
        assert(messages == output)

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
