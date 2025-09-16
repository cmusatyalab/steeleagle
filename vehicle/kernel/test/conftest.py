import asyncio
import pytest
import pytest_asyncio
# Helper import
from helpers import wait_for_services
# Protocol import
import steeleagle_sdk.protocol.testing.testing_pb2 as test_proto

import logging
logger = logging.getLogger(__name__)

'''
Test fixture methods.
'''
@pytest.fixture(autouse=True)
def set_env(monkeypatch, request):
    import os
    configs = os.listdir('./configs/')
    files = [
        ('CONFIGPATH', 'config.toml'),
        ('INTERNALPATH', 'internal.toml'),
        ('LAWPATH', 'laws.toml')
    ]
    for env, file in files:
        name = request.module.__name__
        if not os.path.exists(f'./configs/{name}/{file}'):
            name = 'default' # Use the default configs if there is no override
        monkeypatch.setenv(env, f'./configs/{name}/{file}')

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
    from mocks.mock_clients.mock_swarm_controller import MockSwarmController
    sc = MockSwarmController(command_socket, messages)
    yield sc

@pytest_asyncio.fixture(scope='function')
async def mock_services(messages, command_socket):
    from mocks.serve_mock_services import serve_mock_services
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
    from mocks.mock_clients.mock_mission_client import MockMissionClient
    mission = MockMissionClient(messages)
    yield mission

@pytest_asyncio.fixture(scope='function')
async def kernel(mock_services, command_socket):
    import subprocess
    # List of services to start in the background
    running = []
    subps = [
        ["python", "../main.py"]
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

@pytest_asyncio.fixture(scope='function')
async def imagery():
    from util.sockets import setup_zmq_socket, SocketOperation
    import zmq
    import zmq.asyncio
    # Set up command_socket to connect to the imagery stream
    imagery_socket = zmq.asyncio.Context().socket(zmq.PUB)
    setup_zmq_socket(
        imagery_socket,
        'internal.streams.imagery',
        SocketOperation.BIND
        )
    yield imagery_socket
    imagery_socket.close()

@pytest_asyncio.fixture(scope='function')
async def driver_telemetry():
    from util.sockets import setup_zmq_socket, SocketOperation
    import zmq
    import zmq.asyncio
    # Set up command_socket to connect to the driver telemetry stream
    driver_telemetry_socket = zmq.asyncio.Context().socket(zmq.PUB)
    setup_zmq_socket(
        driver_telemetry_socket,
        'internal.streams.driver_telemetry',
        SocketOperation.BIND
        )
    yield driver_telemetry_socket
    driver_telemetry_socket.close()

@pytest_asyncio.fixture(scope='function')
async def mission_telemetry():
    from util.sockets import setup_zmq_socket, SocketOperation
    import zmq
    import zmq.asyncio
    # Set up command_socket to connect to the mission_telemetry stream
    mission_telemetry_socket = zmq.asyncio.Context().socket(zmq.PUB)
    setup_zmq_socket(
        mission_telemetry_socket,
        'internal.streams.mission_telemetry',
        SocketOperation.BIND
        )
    yield mission_telemetry_socket
    mission_telemetry_socket.close()

@pytest_asyncio.fixture(scope='function')
async def results():
    from util.sockets import setup_zmq_socket, SocketOperation
    import zmq
    import zmq.asyncio
    # Set up command_socket to connect to the result stream
    result_socket = zmq.asyncio.Context().socket(zmq.SUB)
    result_socket.setsockopt(zmq.SUBSCRIBE, b'')
    setup_zmq_socket(
        result_socket,
        'internal.streams.results',
        SocketOperation.CONNECT
        )
    result_socket.RCVTIMEO = 1000 # Millisecond timeout
    yield result_socket
    result_socket.close()

@pytest_asyncio.fixture(scope='function')
async def gabriel(messages):
    from gabriel_protocol.gabriel_pb2 import PayloadType, ResultWrapper
    from gabriel_server import local_engine
    from gabriel_server import cognitive_engine
    from message_sequencer import MessageSequencer, Topic 
    from util.config import query_config
    from multiprocessing import Process
    # Sequencer cognitive engine for writing what we see
    class RepeaterEngine(cognitive_engine.Engine):
        def __init__(self, name):
            super().__init__()
            self._name = name

        def handle(self, input_frame):
            status = ResultWrapper.Status.SUCCESS
            result_wrapper = cognitive_engine.create_result_wrapper(status)
            result = ResultWrapper.Result()
            result.payload_type = input_frame.payload_type
            result_wrapper.results.append(result)
            result_wrapper.result_producer_name.value = self._name
            return result_wrapper
    # Run remote server
    remote_task = Process(target=local_engine.run, args=(
            lambda: RepeaterEngine('REMOTE'),
            'telemetry',
            60, 
            query_config('cloudlet.remote_compute_service').split(':')[-1],
            2,),
            kwargs={
                'use_zeromq' : True
            }
            )
    # Run local server
    local_task = Process(target=local_engine.run, args=(
            lambda: RepeaterEngine('LOCAL'),
            'telemetry',
            60, None, 2,),
            kwargs={
                'use_zeromq' : True,
                'ipc_path' : query_config('internal.streams.local_compute').replace('unix://', '')
            }
            )
    remote_task.start()
    local_task.start()
    yield
    remote_task.terminate()
    remote_task.join()
    local_task.terminate()
    local_task.join()
