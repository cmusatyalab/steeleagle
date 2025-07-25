import time
import asyncio
import grpc
import zmq
import zmq.asyncio
from concurrent import futures
# Service imports
from kernel.control.report_service import ReportService
from kernel.control.control_service_proxy import ControlServiceProxy
from kernel.control.swarm_control_handler_service import SwarmControlHandlerService
# Utility imports
from util.config import query_config, check_config
from util.custom_logger import CustomLogger
from util.sockets import setup_zmq_socket, SocketOperation
from util.auth import ControlAuth
# Protocol imports
from python_bindings import control_pb2 as control_proto
from python_bindings.report_service_pb2_grpc import add_ReportServicer_to_server
from python_bindings.mission_service_pb2_grpc import MissionStub
from python_bindings.driver_service_pb2_grpc import DriverStub, add_DriverServicer_to_server

class ControlMode:
    '''
    Mode switch to determine which entity has control of the vehicle.
    Must be wrapped in a class so it is pass-by-reference.
    -----------------------------------------------
    ControlMode.REMOTE -> Swarm Controller commands
    ControlMode.LOCAL -> Mission commands
    ControlMode.RC -> Remote control joystick commands
    -----------------------------------------------
    '''
    def __init__(self, mode=control_proto.ControlMode.REMOTE):
        self._mode = mode

    def get_mode(self):
        return self._mode

    def switch_mode(self, mode):
        self._mode = mode

mode = ControlMode()

# Create ZeroMQ socket that connects to the Swarm Controller
command_socket = zmq.Context().socket(zmq.DEALER)
setup_zmq_socket(
    command_socket,
    'cloudlet.swarm_controller.endpoint',
    SocketOperation.CONNECT
    )

# Custom logger object
base_logger = CustomLogger()

async def serve_swarm_control_handler_service():
    '''
    Serves the swarm control handler service. Handles input from the Swarm Controller 
    for remote operation, mission start/stop, and mission notification.
    '''
    # Read relevant endpoints from the config
    driver_addr = query_config('internal.control_service.endpoint')
    mission_addr = query_config('internal.mission_service.endpoint')

    # Setup logger
    logger = base_logger.get_logger('/kernel/swarm_control_handler_service')

    # Setup clients
    async with grpc.aio.insecure_channel(driver_addr) as driver_channel, \
            grpc.aio.insecure_channel(mission_addr) as mission_channel:
        # Get the driver stub wrapper which will help us translate
        # Swarm Controller commands into stub calls
        driver_stub = DriverStub(driver_channel)

        # Get the mission stub
        mission_stub = MissionStub(mission_channel) 

        # Build the Swarm Control handler service
        server = SwarmControlHandlerService(
                driver_stub,
                mission_stub,
                mode,
                command_socket,
                logger
                )
    
        # Run the server
        logger.info('Created swarm control handler server! Running service...')
        try:
            await server.start()
        except Exception as e:
            logger.error('Swarm control handler server failed to start, reason: {e}')
        try:
            await server.wait_for_termination()
        except asyncio.exceptions.CancelledError:
            pass
     
async def serve_report_service():
    '''
    Serves the report service. This service allows to mission to send events
    to the Swarm Controller for coordination.
    '''
    # Read relevant endpoint from the config
    host_addr = query_config(
            'services.report_service.endpoint'
            ).split(':')[-1]
    host_url = f'[::]:{host_addr}'

    # Setup logger
    logger = base_logger.get_logger('/kernel/report_service')

    # Setup the server
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    add_ReportServicer_to_server(ReportService(command_socket, logger), server)
    server.add_insecure_port(host_url)
    
    # Run the server
    logger.info('Created report server! Running service...')
    try:
        await server.start()
    except Exception as e:
        logger.error('Report server failed to start, reason: {e}')
    try:
        await server.wait_for_termination()
    except asyncio.exceptions.CancelledError:
        await server.stop(1)

async def serve_control_service():
    '''
    Serves the control proxy service. This service provides an interface
    to send actuation commands to the driver. It also features
    access control via interceptors.
    '''
    # Read relevant endpoints from the config
    driver_addr = query_config('internal.control_service.endpoint')
    host_addr = query_config(
            'services.control_service.endpoint'
            ).split(':')[-1]
    host_url = f'[::]:{host_addr}'
    
    # Setup logger
    logger = base_logger.get_logger('/kernel/control_service')

    # Create a channel to the driver
    async with grpc.aio.insecure_channel(driver_addr) as channel:
        # Set up an interceptor for control authorization
        interceptor = [ControlAuth(mode, logger)]

        # Get the driver stub
        stub = DriverStub(channel)

        # Setup the server
        server = grpc.aio.server(
                futures.ThreadPoolExecutor(max_workers=10),
                interceptors=interceptor
                )
        add_DriverServicer_to_server(ControlServiceProxy(stub, logger), server)
        server.add_insecure_port(host_url)
        
        # Run the server
        logger.info('Created control server! Running service...')
        try:
            await server.start()
        except Exception as e:
            logger.error('Control server failed to start, reason: {e}')
        try:
            await server.wait_for_termination()
        except asyncio.exceptions.CancelledError:
            await server.stop(3)

async def main():
    try:
        sc_handler_service = asyncio.create_task(serve_swarm_control_handler_service()) 
        report_service = asyncio.create_task(serve_report_service())
        control_service = asyncio.create_task(serve_control_service())
        await asyncio.gather(sc_handler_service, report_service, control_service)
    except asyncio.exceptions.CancelledError:
        sc_handler_service.cancel()
        report_service.cancel()
        control_service.cancel()
        await asyncio.gather(sc_handler_service, report_service, control_service)

if __name__ == "__main__":
    if check_config():
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print('\nControl manager cancelled, all services shut down.')
