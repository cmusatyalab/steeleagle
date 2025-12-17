import asyncio
import grpc
from concurrent import futures
import zmq
import zmq.asyncio
import logging

# Mock import
from test.message_sequencer import Topic, MessageSequencer
from test.mocks.generate_mock_service import generate_mock_service

generate_mock_service("Control", "control_service")
from test.mocks.mock_services._gen_mock_control_service import MockControlService

generate_mock_service("Mission", "mission_service")
from test.mocks.mock_services._gen_mock_mission_service import MockMissionService

# Utility import
from util.sockets import setup_zmq_socket, SocketOperation
from util.config import query_config

# Protocol import
from steeleagle_sdk.protocol.services.control_service_pb2_grpc import (
    add_ControlServicer_to_server,
)
from steeleagle_sdk.protocol.services.mission_service_pb2_grpc import (
    add_MissionServicer_to_server,
)
import steeleagle_sdk.protocol.testing.testing_pb2 as test_proto

logger = logging.getLogger(__name__)


async def serve_mock_services(messages):
    server = grpc.aio.server(
        futures.ThreadPoolExecutor(max_workers=10),
    )
    add_ControlServicer_to_server(
        MockControlService(MessageSequencer(Topic.DRIVER_CONTROL_SERVICE, messages)),
        server,
    )
    add_MissionServicer_to_server(
        MockMissionService(MessageSequencer(Topic.MISSION_SERVICE, messages)), server
    )
    server.add_insecure_port(query_config("internal.services.driver"))
    server.add_insecure_port(query_config("internal.services.mission"))
    try:
        await server.start()
    except Exception as e:
        logger.error(f"Mock services failed to start, reason: {e}")
        return
    # Create ZeroMQ socket that connects to the test apparatus
    command_socket = zmq.asyncio.Context().socket(zmq.DEALER)
    command_socket.setsockopt(zmq.IDENTITY, "mock_services".encode("utf-8"))
    setup_zmq_socket(
        command_socket, "cloudlet.swarm_controller", SocketOperation.CONNECT
    )
    # Notify the test bench
    service = test_proto.ServiceReady(
        readied_service=test_proto.ServiceType.DRIVER_CONTROL_SERVICE
    )
    logger.debug("mock_driver_control_service ready for testing!")
    command_socket.send(service.SerializeToString())
    service = test_proto.ServiceReady(
        readied_service=test_proto.ServiceType.MISSION_SERVICE
    )
    logger.debug("mock_mission_service ready for testing!")
    command_socket.send(service.SerializeToString())
    try:
        await server.wait_for_termination()
    except asyncio.exceptions.CancelledError:
        await server.stop(1)
        logger.info("Mock services shut down.")
