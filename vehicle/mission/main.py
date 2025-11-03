import asyncio
from concurrent import futures
import grpc
import logging
# Protocol imports
from steeleagle_sdk.protocol.services import control_service_pb2, control_service_pb2_grpc
from steeleagle_sdk.protocol.services import mission_service_pb2, mission_service_pb2_grpc
from steeleagle_sdk.protocol.services import report_service_pb2, report_service_pb2_grpc
from steeleagle_sdk.protocol.services import compute_service_pb2, compute_service_pb2_grpc
from mission.mission_service import MissionService

# Utility import
from util.log import setup_logging
setup_logging()
from util.config import query_config

logger = logging.getLogger("mission/main")

async def main():
    # setup the stubs
    stub_channel = grpc.aio.insecure_channel(query_config('internal.services.kernel'))
    ctrl_stub = control_service_pb2_grpc.ControlStub(stub_channel)
    compute_stub = compute_service_pb2_grpc.ComputeStub(stub_channel)
    report_stub = report_service_pb2_grpc.ReportStub(stub_channel)
    context = {}
    context['control'] = ctrl_stub
    context['compute'] = compute_stub
    context['report'] = report_stub

    # Define the server that will hold our services
    server = grpc.aio.server(migration_thread_pool=futures.ThreadPoolExecutor(max_workers=10))

    # Create and assign the services to the server
    mission_service_pb2_grpc.add_MissionServicer_to_server(MissionService(context), server)

    # Add main channel to server
    server.add_insecure_port(query_config('internal.services.mission'))
    
    # Start services
    await server.start()
    logger.info('Services started!')
    
    try:
        await server.wait_for_termination()
    except (SystemExit, asyncio.exceptions.CancelledError):
        logger.info('Shutting down...')
        await server.stop(1)

if __name__ == "__main__":
    asyncio.run(main())
