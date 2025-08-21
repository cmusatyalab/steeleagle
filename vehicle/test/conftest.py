import asyncio
import pytest
import pytest_asyncio
# Helper import
from helpers import wait_for_services
# Protocol import
import bindings.python.testing.testing_pb2 as test_proto

import logging
logger = logging.getLogger(__name__)

'''
Test fixture methods.
'''
@pytest.fixture(autouse=True)
def set_env(monkeypatch, request):
    name = request.module.__name__
    monkeypatch.setenv('CONFIGPATH', f'./configs/{name}/config.toml')
    monkeypatch.setenv('INTERNALPATH', f'./configs/{name}/internal.toml')
    monkeypatch.setenv('LAWPATH', f'./configs/{name}/laws.toml')

@pytest.fixture(scope='function')
def messages():
    messages = []
    yield messages

@pytest.fixture(scope='function')
def command_socket():
    from util.sockets import setup_zmq_socket, SocketOperation
    import zmq
    import zmq.asyncio
    # Set up command_socket to connect to the kernel
    command_socket = zmq.asyncio.Context().socket(zmq.ROUTER)
    setup_zmq_socket(
        command_socket,
        'cloudlet.swarm_controller',
        SocketOperation.BIND
        )
    yield command_socket
    command_socket.close()

@pytest.fixture(scope='function')
def swarm_controller(messages, command_socket):
    from mock_clients.mock_swarm_controller import MockSwarmController
    sc = MockSwarmController(command_socket, messages)
    yield sc

@pytest_asyncio.fixture(scope='function')
async def mock_services(messages, command_socket):
    from mock_services.serve_mock_services import serve_mock_services
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
    import time
    import subprocess
    # List of services to start in the background
    running = []
    subps = [
        ["python3", "../core/main.py"]
        ]

    for subp in subps:
        s = subprocess.Popen(subp)
        running.append(s)
        await asyncio.sleep(1)
    # Wait for needed services
    required = [
       test_proto.ServiceType.CORE_SERVICES
    ]
    await wait_for_services(required, command_socket)
    yield
    for subp in running:
        subp.terminate()
        subp.wait()
