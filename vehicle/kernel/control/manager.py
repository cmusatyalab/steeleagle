import time
import asyncio
import grpc
import zmq
import zmq.asyncio
import argparse
from concurrent import futures
import importlib
# Service imports
from kernel.control.report_service import ReportService
from kernel.control.control_service_proxy import ControlServiceProxy
from kernel.control.swarm_control_handler_service import SwarmControlHandlerService
# Utility imports
from util.config import query_config, check_config
from util.rpc import get_bind_addr
from util.log import get_logger
from util.sockets import setup_zmq_socket, SocketOperation
from util.auth import ControlAuth, ControlMode
from util.cleanup import register_cleanup_handler
# Protocol imports
from google.protobuf.json_format import ParseDict
from python_bindings.report_service_pb2_grpc import add_ReportServicer_to_server
from python_bindings.control_service_pb2 import HoldRequest
from python_bindings.control_service_pb2_grpc import ControlStub, add_ControlServicer_to_server

# Import test infra if needed
if query_config('internal.testing.status'):
    from python_bindings import testing_pb2 as test_proto

# Create ZeroMQ socket that connects to the Swarm Controller
command_socket = zmq.asyncio.Context().socket(zmq.DEALER)
command_socket.setsockopt(
        zmq.IDENTITY,
        query_config('vehicle.name').encode("utf-8")
        )
setup_zmq_socket(
    command_socket,
    'cloudlet.swarm_controller.endpoint',
    SocketOperation.CONNECT
    )

async def serve_report_service():
    '''
    Serves the report service. This service allows to mission to send events
    to the Swarm Controller for coordination.
    '''
    # Read relevant endpoint from the config
    host_addr = get_bind_addr(query_config('services.report_service.endpoint'))

    # Setup logger
    logger = get_logger('kernel/report_service')

    # Setup the server
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    add_ReportServicer_to_server(ReportService(command_socket, logger), server)
    server.add_insecure_port(host_addr)
    
    # Run the server
    logger.info('Created report server! Running service...')
    try:
        await server.start()
    except Exception as e:
        logger.error('Report server failed to start, reason: {e}')
        return
    if query_config('internal.testing.status'):
        # Create ZeroMQ socket that connects to the test apparatus
        test_socket = zmq.asyncio.Context().socket(zmq.DEALER)
        test_socket.setsockopt(
                zmq.IDENTITY,
                'report_service'.encode("utf-8")
                )
        setup_zmq_socket(
            test_socket,
            'internal.testing.endpoint',
            SocketOperation.CONNECT
            )
        # Notify the test bench
        service = test_proto.ServiceReady(
                readied_service=test_proto.ServiceType.REPORT_SERVICE
                )
        logger.debug('report_service ready for testing!')
        test_socket.send(service.SerializeToString())
    try:
        await server.wait_for_termination()
    except asyncio.exceptions.CancelledError:
        logger.info('Report server shut down.')

async def serve_control_service():
    '''
    Serves the control proxy and Swarm Controller handler services.
    These services provide an interface to send actuation commands to the 
    driver from the mission, and an interface for the Swarm Controller
    to access any service over ZeroMQ, respectively. The Swarm Controller
    handler service also manages control authorization over the vehicle.
    '''
    try:
        # Setup logger
        logger = get_logger('kernel/control_service')

        # Build a control authorization object
        auth = ControlAuth(logger)

        # Start the sub-services
        logger.info('Starting sub-services...')
        sc_handler_service = asyncio.create_task(
                serve_swarm_control_handler_service(auth, logger)
                )
        control_proxy_service = asyncio.create_task(
                serve_control_proxy_service(auth, logger)
                )
        await asyncio.gather(sc_handler_service, control_proxy_service)
    except asyncio.exceptions.CancelledError:
        sc_handler_service.cancel()
        control_proxy_service.cancel()
        await asyncio.gather(sc_handler_service, control_proxy_service)
        logger.info('All control sub-services shut down.')

async def serve_swarm_control_handler_service(auth, logger):
    # Get the services that can be accessed by the Swarm Controller
    allowed_protos = query_config('internal.remote_control.allowed_protos')
    
    # Create a call table that associates request names with a stub;
    # this allows easy multiplexing of Swarm Controller commands, and
    # enables dynamic remote control of local gRPC servers
    channels = []
    call_table = {}
    for proto in allowed_protos:
        try:
            service_module = importlib.import_module(
                    f"python_bindings.{proto}_pb2"
                    )
            stub_module = importlib.import_module(
                    f"python_bindings.{proto}_pb2_grpc"
                    )
        except:
            raise ValueError(
                    'Could not load {proto} from allowed_protos. Check your .internal.yaml!'
                    )
            return
        for service in service_module.DESCRIPTOR.services_by_name:
            # Create the stub and connect it to the corresponding endpoint
            channel = grpc.aio.insecure_channel(
                    query_config(f"internal.{proto}.endpoint")
                    )
            channels.append(channel)
            stub = getattr(stub_module, f"{service}Stub")(channel)
            service_obj = getattr(service_module, f"_{service.upper()}")
            
            # Associate service methods with this stub and service
            for m in service_obj.methods:
                full_name = f'{proto}.{m.name}'
                call_table[full_name] = getattr(stub, m.name)
    
    # Build a failsafe request to send if the swarm controller is disconnected
    failsafe = None
    if query_config(f'internal.failsafe.method'):
        # Read in the failsafe info from .internal.yaml
        failsafe_service, failsafe_method = \
                query_config(f'internal.failsafe.method').split('.')
        failsafe_params = query_config(f'internal.failsafe.params')
        
        try:
            # Import the required modules
            failsafe_service_module = importlib.import_module(
                    f'python_bindings.{failsafe_service}_pb2'
                    )
            failsafe_stub_module = importlib.import_module(
                    f'python_bindings.{failsafe_service}_pb2_grpc'
                    )
            failsafe_request = getattr(
                    failsafe_service_module,
                    f'{failsafe_method}Request'
                    )()
        except:
            raise ValueError(
                    'Could not import failsafe module. Check your .internal.yaml!'
                    )
            return
        
        try:
            ParseDict(failsafe_params, failsafe_request)
            timeout = query_config('internal.failsafe.timeout')
            if type(timeout) == float or type(timeout) == int and timeout > 0:
                failsafe = (failsafe_method, failsafe_request, timeout)
            else:
                # Set timeout to 1 second if no timeout is provided
                failsafe = (failsafe_method, failsafe_request, 1.0)
            # Search the corresponding service file for the correct method, and add the
            # stub to the call table
            failsafe_set = False
            for service in failsafe_service_module.DESCRIPTOR.services_by_name:
                service_obj = getattr(failsafe_service_module, f'_{service.upper()}')
                for m in service_obj.methods:
                    if m.name == failsafe_method:
                        full_name = f'{failsafe_service}.{failsafe_method}'
                        channel = grpc.aio.insecure_channel(
                                query_config(f'internal.{failsafe_service}.endpoint')
                                )
                        channels.append(channel)
                        stub = getattr(failsafe_stub_module, f'{service}Stub')(channel)
                        call_table[full_name] = getattr(stub, m.name)
                        failsafe_set = True
        except:
            raise ValueError(
                    'Failsafe params not loaded correctly. Check your .internal.yaml!'
                    )
            return
        if not failsafe_set:
            raise ValueError(
                    'Failsafe method not found in services. Check your .internal.yaml!'
                    )
            return
    else:
        logger.warning(
                'FAILSAFE DISABLED: Ensure that a failsafe is set when using a real vehicle.'
                )

    # Build the Swarm Control handler service
    server = SwarmControlHandlerService(
            auth,
            command_socket,
            call_table,
            logger,
            failsafe=failsafe
            )
    
    # Run the server
    logger.info('Created swarm control handler server! Running service...')
    try:
        await server.start()
    except Exception as e:
        logger.error('Swarm control handler server failed to start, reason: {e}')
        return
    if query_config('internal.testing.status'):
        # Create ZeroMQ socket that connects to the test apparatus
        test_socket = zmq.asyncio.Context().socket(zmq.DEALER)
        test_socket.setsockopt(
                zmq.IDENTITY,
                'swarm_control_handler_service'.encode("utf-8")
                )
        setup_zmq_socket(
            test_socket,
            'internal.testing.endpoint',
            SocketOperation.CONNECT
            )
        # Notify the test bench
        service = test_proto.ServiceReady(
                readied_service=test_proto.ServiceType.SC_HANDLER_SERVICE
                )
        logger.debug('swarm_control_handler_service ready for testing!')
        test_socket.send(service.SerializeToString())
    try:
        await server.wait_for_termination()
    except asyncio.exceptions.CancelledError:
        for channel in channels:
            await channel.close()
        logger.info('Swarm control handler server shut down.')

async def serve_control_proxy_service(auth, logger):
    # Read relevant endpoints from the config
    control_addr = query_config('internal.control_service.endpoint')
    host_addr = get_bind_addr(query_config('services.control_service.endpoint'))

    # Create a channel to the driver
    async with grpc.aio.insecure_channel(control_addr) as channel:
        # Set up an interceptor for control authorization
        interceptor = [auth]

        # Get the driver stub
        stub = ControlStub(channel)

        # Setup the server
        server = grpc.aio.server(
                futures.ThreadPoolExecutor(max_workers=10),
                interceptors=interceptor
                )
        add_ControlServicer_to_server(ControlServiceProxy(stub, logger), server)
        server.add_insecure_port(host_addr)
        
        # Run the server
        logger.info('Created control proxy server! Running service...')
        try:
            await server.start()
        except Exception as e:
            logger.error('Control proxy server failed to start, reason: {e}')
            return
        if query_config('internal.testing.status'):
            # Create ZeroMQ socket that connects to the test apparatus
            test_socket = zmq.asyncio.Context().socket(zmq.DEALER)
            test_socket.setsockopt(
                    zmq.IDENTITY,
                    'control_proxy_service'.encode("utf-8")
                    )
            setup_zmq_socket(
                test_socket,
                'internal.testing.endpoint',
                SocketOperation.CONNECT
                )
            # Notify the test bench
            service = test_proto.ServiceReady(
                    readied_service=test_proto.ServiceType.CONTROL_PROXY_SERVICE
                    )
            logger.debug('control_proxy_service ready for testing!')
            test_socket.send(service.SerializeToString())
        try:
            await server.wait_for_termination()
        except asyncio.exceptions.CancelledError:
            logger.info('Control proxy server shut down.')

async def main():
    # Allows graceful shutdown on SIGTERM
    register_cleanup_handler()

    try:
        report_service = asyncio.create_task(serve_report_service())
        control_service = asyncio.create_task(serve_control_service())
        await asyncio.gather(report_service, control_service)
    except:
        report_service.cancel()
        control_service.cancel()
        await asyncio.gather(report_service, control_service)

if __name__ == "__main__":
    check_config()
    asyncio.run(main())
