import os
import asyncio
import zmq
import zmq.asyncio
import grpc
from concurrent import futures
# Law handler import
from core.laws.authority import LawAuthority
from core.laws.interceptor import LawInterceptor
# Utility import
from util.log import get_logger
from util.cleanup import register_cleanup_handler
register_cleanup_handler() # Cleanup handler for SIGTERM
from util.config import query_config
from util.sockets import setup_zmq_socket, SocketOperation
# Generate proxy files
root = os.getenv('ROOTPATH')
if not root:
    root = '../'
from core.services.proxy_helper import generate_proxy
generate_proxy(
        'Control', 
        'control_service',
        f'{root}vehicle/core/services/_gen_control_service_proxy.py',
        query_config('internal.services.driver')
        )
from core.services._gen_control_service_proxy import ControlProxy
generate_proxy(
        'Mission', 
        'mission_service',
        f'{root}vehicle/core/services/_gen_mission_service_proxy.py',
        query_config('internal.services.mission')
        )
from core.services._gen_mission_service_proxy import MissionProxy
# Service imports
from core.services.report_service import ReportService
from core.services.compute_service import ComputeService
# Proto binding imports
from bindings.python.services import control_service_pb2, control_service_pb2_grpc
from bindings.python.services import mission_service_pb2, mission_service_pb2_grpc
from bindings.python.services import report_service_pb2, report_service_pb2_grpc
from bindings.python.services import compute_service_pb2, compute_service_pb2_grpc
# Remote control handler import
from handlers.remote_control_handler import RemoteControlHandler
from handlers.stream_handler import StreamHandler

logger = get_logger('core/main')

async def main():
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
    
    # Define the server that will hold our services
    server = grpc.aio.server(
            futures.ThreadPoolExecutor(max_workers=10),
            interceptors=law_interceptor
            )
    # Create and assign the services to the server
    control_service_pb2_grpc.add_ControlServicer_to_server(ControlProxy(), server)
    mission_service_pb2_grpc.add_MissionServicer_to_server(MissionProxy(), server)
    report_service_pb2_grpc.add_ReportServicer_to_server(ReportService(command_socket), server)
    compute_service_pb2_grpc.add_ComputeServicer_to_server(ComputeService(), server)
    # Add main channel to server
    server.add_insecure_port(query_config('internal.services.core'))

    # Check if testing is on
    test = query_config('testing')

    # Start services
    await server.start()
    logger.info('Services started!')
    # Send opening commands
    await law_authority.start()
    logger.info('Law authority started!')

    # Create the remote control and stream handler
    rc_handler = RemoteControlHandler(law_authority, command_socket)
    stream_handler = StreamHandler(law_authority)
    await rc_handler.start(query_config('internal.timeouts.server'))
    logger.info('Started handling remote input!')
    await stream_handler.start()
    logger.info('Started handling data streams!')

    # If in test mode, notify the test bench that core services
    # are ready
    if test:
        from bindings.python.testing.testing_pb2 import ServiceReady
        ready = ServiceReady(readied_service=0)
        command_socket.send(ready.SerializeToString())

    try:
        await asyncio.gather(
                server.wait_for_termination(),
                rc_handler.wait_for_termination(),
                stream_handler.wait_for_termination()
                )
    except (SystemExit, asyncio.exceptions.CancelledError):
        logger.info('Shutting down...')
        await server.stop(1)
    
if __name__ == "__main__":
    asyncio.run(main())
