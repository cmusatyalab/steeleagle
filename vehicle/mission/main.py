# Proto binding imports
import grpc
from steeleagle_sdk.protocol.services import control_service_pb2, control_service_pb2_grpc
from steeleagle_sdk.protocol.services import mission_service_pb2, mission_service_pb2_grpc
from steeleagle_sdk.protocol.services import report_service_pb2, report_service_pb2_grpc
from steeleagle_sdk.protocol.services import compute_service_pb2, compute_service_pb2_grpc
from mission.mission_service import MissionService
from core.laws.interceptor import LawInterceptor
from core.laws.authority import LawAuthority
import asyncio
from util.log import get_logger
from util.config import query_config
from concurrent import futures

logger = get_logger('mission/main')
async def main():
    # setup the stubs
    stub_channel = grpc.insecure_channel(query_config('internal.services.core'))
    ctrl_stub = control_service_pb2_grpc.ControlStub(stub_channel)
    compute_stub = compute_service_pb2_grpc.ComputeStub(stub_channel)
    report_stub = report_service_pb2_grpc.ReportStub(stub_channel)
    context = {}
    context['Ctrl']=ctrl_stub
    context['Cpt'] = compute_stub
    context['Rpt'] = report_stub

    # Define the server that will hold our services
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))

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
