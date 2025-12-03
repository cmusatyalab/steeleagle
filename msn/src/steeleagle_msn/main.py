import asyncio
from concurrent import futures
import grpc
import logging
# Protocol imports
from steeleagle_sdk.protocol.services import mission_service_pb2_grpc
from .mission_service import MissionService
logger = logging.getLogger("mission/main")

async def main():
    address = {}
    address['vehicle'] = 'unix:///tmp/kernel.sock' 
    address['telemetry'] = 'unix:///tmp/driver_telem.sock'
    address['results'] = 'unix:///tmp/results.sock'

    # Define the server that will hold our services
    server = grpc.aio.server(migration_thread_pool=futures.ThreadPoolExecutor(max_workers=10))

    # Create and assign the services to the server
    mission_service_pb2_grpc.add_MissionServicer_to_server(MissionService(address), server)

    # Add main channel to server
    server.add_insecure_port('unix:///tmp/mission.sock')
    
    # Start services
    await server.start()
    logger.info('Services started!')
    
    try:
        await server.wait_for_termination()
    except (SystemExit, asyncio.exceptions.CancelledError):
        logger.info('Shutting down...')
        await server.stop(1)

def cli():
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())
