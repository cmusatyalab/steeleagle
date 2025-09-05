# Proto binding imports
from bindings.python.services import control_service_pb2, control_service_pb2_grpc
from bindings.python.services import mission_service_pb2, mission_service_pb2_grpc
from bindings.python.services import report_service_pb2, report_service_pb2_grpc
from bindings.python.services import compute_service_pb2, compute_service_pb2_grpc
from mission_service import MissionService
import asyncio
from  util.log import get_logger

logger = get_logger('mission/main')
async def main():
    # setup the stubs
    stub_channel = grpc.insecure_channel(query_config('internal.services.core'))
    ctrl_stub = control_service_pb2_grpc.ControlStub()
    compute_stub = compute_service_pb2_grpc.ComputeStub()
    report_stub = report_service_pb2_grpc.ReportStub()
    context['Ctrl']=ctrl_stub
    context['Cpt'] = compute_stub
    context['Rpt'] = report_stub

    # Define the server that will hold our services
    server = grpc.aio.server(
            futures.ThreadPoolExecutor(max_workers=10),
            interceptors=law_interceptor
            )
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
