import os
import asyncio
import zmq
import zmq.asyncio
import grpc
import argparse
import logging
from concurrent import futures
from multiprocessing import Process
# Law handler import
from kernel.laws.authority import LawAuthority
from kernel.laws.interceptor import LawInterceptor
# Utility import
from util.cleanup import register_cleanup_handler
register_cleanup_handler() # Cleanup handler for SIGTERM
from util.config import query_config
from util.sockets import setup_zmq_socket, SocketOperation
from util.log import setup_logging
setup_logging()
# Generate proxy files
from kernel.services.generate_proxy import generate_proxy
generate_proxy('Control', 'control_service', query_config('internal.services.driver'))
from kernel.services._gen_control_service_proxy import ControlProxy
generate_proxy('Mission', 'mission_service', query_config('internal.services.mission'))
from kernel.services._gen_mission_service_proxy import MissionProxy
# Service imports
from kernel.services.report_service import ReportService
from kernel.services.compute_service import ComputeService
# Proto binding imports
from steeleagle_sdk.protocol.services import control_service_pb2_grpc
from steeleagle_sdk.protocol.services import mission_service_pb2_grpc
from steeleagle_sdk.protocol.services import report_service_pb2_grpc
from steeleagle_sdk.protocol.services import compute_service_pb2_grpc
# Remote control handler import
from handlers.command_handler import CommandHandler
from handlers.stream_handler import StreamHandler

logger = logging.getLogger('kernel/main')

async def main(args):
    # Create ZeroMQ socket that connects to the Swarm Controller
    command_socket = zmq.asyncio.Context().socket(zmq.DEALER)
    command_socket.setsockopt(
            zmq.IDENTITY,
            query_config('vehicle.name').encode("utf-8")
            )
    setup_zmq_socket(
        command_socket,
        'cloudlet.swarm_controller',
        SocketOperation.CONNECT
        )
    
    # Create the global law handler
    law_authority = LawAuthority()
    # Set up the law interceptor
    law_interceptor = [LawInterceptor(law_authority)]
    # Create the remote control and stream handler
    rc_handler = CommandHandler(law_authority, command_socket)
    stream_handler = StreamHandler(law_authority)
    
    # Define the server that will hold our services
    server = grpc.aio.server(
            migration_thread_pool=futures.ThreadPoolExecutor(max_workers=10),
            interceptors=law_interceptor
            )
    # Create and assign the services to the server
    control_service_pb2_grpc.add_ControlServicer_to_server(ControlProxy(), server)
    mission_service_pb2_grpc.add_MissionServicer_to_server(MissionProxy(), server)
    report_service_pb2_grpc.add_ReportServicer_to_server(ReportService(command_socket), server)
    compute_service_pb2_grpc.add_ComputeServicer_to_server(ComputeService(stream_handler), server)
    # Add main channel to server
    server.add_insecure_port(query_config('internal.services.kernel'))

    # Start services
    await server.start()
    logger.info('Services started!')

    try:
        # Send opening commands
        success = await law_authority.start(args.startup)
        if not success:
            raise SystemExit(1)
        logger.info('Device connected!')

        try:
            await rc_handler.start(query_config('internal.timeouts.server'))
        except ValueError:
            await rc_handler.start(failsafe_timeout=None)
        logger.info('Started handling remote input!')
        await stream_handler.start()
        logger.info('Started handling data streams!')

        # If in test mode, notify the test bench that kernel services
        # are ready
        if args.test:
            from steeleagle_sdk.protocol.testing.testing_pb2 import ServiceReady
            ready = ServiceReady(readied_service=0)
            command_socket.send(ready.SerializeToString())

        await asyncio.gather(
                server.wait_for_termination(),
                rc_handler.wait_for_termination(),
                stream_handler.wait_for_termination()
                )
    except (SystemExit, asyncio.exceptions.CancelledError):
        await server.stop(1)
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Runs core services and handles permissions.")
    parser.add_argument('--test', action='store_true', help='Report when core services are ready for testing')
    parser.add_argument("--startup", nargs="+", default=[], help="List of startup commands to run before entering __BASE__ law")
    args = parser.parse_args()
    logger.info(args.startup)
    asyncio.run(main(args))
