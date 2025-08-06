import asyncio
import grpc
from concurrent import futures
import zmq
import zmq.asyncio
import logging
# Mock import
from grpc_test import MESSAGES
from message_sequencer import Topic, MessageSequencer
from mock_services.mock_control_service import MockControlService
# Utility import
from util.rpc import get_bind_addr
from util.sockets import setup_zmq_socket, SocketOperation
from util.config import query_config
from util.cleanup import register_cleanup_handler
from util.log import get_logger
# Protocol import
from python_bindings.control_service_pb2_grpc import add_ControlServicer_to_server
import python_bindings.testing_pb2 as test_proto

async def start_mock_driver_control_service():
    logger = get_logger('mocks/mock_control_service')
    host_addr = get_bind_addr(query_config('internal.control_service.endpoint'))
    control_service = grpc.aio.server(
            futures.ThreadPoolExecutor(max_workers=10),
            )
    control_seq = MessageSequencer(
            Topic.DRIVER_CONTROL_SERVICE,
            MESSAGES
            )
    add_ControlServicer_to_server(MockControlService(control_seq, logger), control_service)
    control_service.add_insecure_port(host_addr)
    try:
        await control_service.start()
    except Exception as e:
        logger.error('Mock control service failed to start, reason: {e}')
        return
    # Create ZeroMQ socket that connects to the test apparatus
    test_socket = zmq.asyncio.Context().socket(zmq.DEALER)
    test_socket.setsockopt(
            zmq.IDENTITY,
            'mock_control_service'.encode("utf-8")
            )
    setup_zmq_socket(
        test_socket,
        'internal.testing.endpoint',
        SocketOperation.CONNECT
        )
    service = test_proto.ServiceReady(
            readied_service=test_proto.ServiceType.DRIVER_CONTROL_SERVICE
            )
    # Notify the test bench
    logger.debug('mock_control_service ready for testing!')
    test_socket.send(service.SerializeToString())
    try:
        await control_service.wait_for_termination()
    except asyncio.exceptions.CancelledError:
        await control_service.stop(1)
        logger.info('Mock control service shut down.')

async def main():
    # Allows graceful shutdown on SIGTERM
    register_cleanup_handler()

    try:
        driver_service = asyncio.create_task(start_mock_driver_control_service())
        await driver_service
    except:
        driver_service.cancel()
        await driver_service

if __name__ == "__main__":
    asyncio.run(main())
