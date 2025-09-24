import os
import asyncio
import zmq
import zmq.asyncio
import grpc
from concurrent import futures
from multiprocessing import Process
# Law handler import
from kernel.laws.authority import LawAuthority
from kernel.laws.interceptor import LawInterceptor
# Utility import
from util.log import get_logger
from util.cleanup import register_cleanup_handler
register_cleanup_handler() # Cleanup handler for SIGTERM
from util.config import query_config
from util.sockets import setup_zmq_socket, SocketOperation
# Generate proxy files
from kernel.services.generate_proxy import generate_proxy
generate_proxy('Control', 'control_service', query_config('internal.services.driver'))
from kernel.services._gen_control_service_proxy import ControlProxy
generate_proxy('Mission', 'mission_service', query_config('internal.services.mission'))
from kernel.services._gen_mission_service_proxy import MissionProxy
# Service imports
from kernel.services.report_service import ReportService
from kernel.services.compute_service import ComputeService
from kernel.services.flight_log_service import FlightLogService
# Proto binding imports
from steeleagle_sdk.protocol.services import control_service_pb2_grpc
from steeleagle_sdk.protocol.services import mission_service_pb2_grpc
from steeleagle_sdk.protocol.services import report_service_pb2_grpc
from steeleagle_sdk.protocol.services import compute_service_pb2_grpc
from steeleagle_sdk.protocol.services import flight_log_service_pb2_grpc
# Remote control handler import
from handlers.command_handler import CommandHandler
from handlers.stream_handler import StreamHandler

logger = get_logger('kernel/main')

def attach_logger():
    '''
    Attaches the flight log service to the flight log endpoint. This allows
    any process within the vehicle to log via gRPC to an MCAP file which
    is written during kernel shutdown.
    '''
    # Make sure this process has access to system exit
    register_cleanup_handler()
    # Define the log server
    log_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    flight_log_service_pb2_grpc.add_FlightLogServicer_to_server(FlightLogService(), log_server)
    # Add log channel to server
    log_server.add_insecure_port(query_config('internal.services.flight_log'))
    log_server.start()
    try:
        log_server.wait_for_termination()
    except SystemExit:
        log_server.stop(1)

async def main():
    # Create the logger in the background
    log_process = Process(target=attach_logger, daemon=True)
    log_process.start()
    # Give it time to start up
    await asyncio.sleep(0.1)

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
            futures.ThreadPoolExecutor(max_workers=10),
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
        success = await law_authority.start()
        if not success:
            raise SystemExit(1)
        logger.info('Device connected!')

        await rc_handler.start(query_config('internal.timeouts.server'))
        logger.info('Started handling remote input!')
        await stream_handler.start()
        logger.info('Started handling data streams!')

        # If in test mode, notify the test bench that kernel services
        # are ready
        if query_config('testing'):
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
        log_process.terminate()
        log_process.join()
    
if __name__ == "__main__":
    asyncio.run(main())
