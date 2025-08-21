import asyncio
import grpc
from concurrent import futures
import zmq
import zmq.asyncio
import logging
import os
# Mock import
from message_sequencer import Topic, MessageSequencer
from mock_services.generate_mock_services import generate_mock_services
root = os.getenv('ROOTPATH')
if not root:
    root = '../../'
generate_mock_services(
        'Control', 
        'control_service',
        f'{root}vehicle/test/mock_services/_gen_mock_control_service.py'
        )
from mock_services._gen_mock_control_service import MockControlService
generate_mock_services(
        'Mission', 
        'mission_service',
        f'{root}vehicle/test/mock_services/_gen_mock_mission_service.py',
        )
from mock_services._gen_mock_mission_service import MockMissionService
# Utility import
from util.sockets import setup_zmq_socket, SocketOperation
from util.config import query_config
from util.cleanup import register_cleanup_handler
from util.log import get_logger
# Protocol import
from python_bindings.control_service_pb2_grpc import add_ControlServicer_to_server
from python_bindings.mission_service_pb2_grpc import add_MissionServicer_to_server
import python_bindings.testing_pb2 as test_proto

logger = get_logger('mocks/start_mocks')

async def serve_mock_services(messages):
    server = grpc.aio.server(
            futures.ThreadPoolExecutor(max_workers=10),
            )
    add_ControlServicer_to_server(
            MockControlService(
                MessageSequencer(
                    Topic.DRIVER_CONTROL_SERVICE,
                    messages
                    )
                ),
            server
            )
    add_MissionServicer_to_server(
            MockMissionService(
                MessageSequencer(
                    Topic.MISSION_SERVICE,
                    messages
                    )
                ),
            server
            )
    server.add_insecure_port(query_config('internal.services.driver'))
    server.add_insecure_port(query_config('internal.services.mission'))
    try:
        await server.start()
    except Exception as e:
        logger.error('Mock services failed to start, reason: {e}')
        return
    # Create ZeroMQ socket that connects to the test apparatus
    command_socket = zmq.asyncio.Context().socket(zmq.DEALER)
    command_socket.setsockopt(
            zmq.IDENTITY,
            'mock_services'.encode("utf-8")
            )
    setup_zmq_socket(
        command_socket,
        'cloudlet.swarm_controller',
        SocketOperation.CONNECT
        )
    # Notify the test bench
    service = test_proto.ServiceReady(
            readied_service=test_proto.ServiceType.DRIVER_CONTROL_SERVICE
            )
    logger.debug('mock_driver_control_service ready for testing!')
    command_socket.send(service.SerializeToString())
    service = test_proto.ServiceReady(
            readied_service=test_proto.ServiceType.MISSION_SERVICE
            )
    logger.debug('mock_mission_service ready for testing!')
    command_socket.send(service.SerializeToString())
    try:
        await server.wait_for_termination()
    except asyncio.exceptions.CancelledError:
        await server.stop(1)
        logger.info('Mock services shut down.')
