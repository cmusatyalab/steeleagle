from DigitalPerfect.DigitalPerfect import DigitalPerfectDrone
import asyncio
from concurrent import futures
import grpc
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("Parrot/main")

# Protocol imports
from services import control_service_pb2_grpc


DRIVER_SOCK = 'unix:///tmp/driver.sock'

async def main():
    logger.info("Starting driver services...")
    server = grpc.aio.server(
        migration_thread_pool=futures.ThreadPoolExecutor(max_workers=10)
    )
    control_service_pb2_grpc.add_ControlServicer_to_server(
        DigitalPerfectDrone("DigitalPerfect"), server
    )
    server.add_insecure_port(DRIVER_SOCK)
    await server.start()
    logger.info("Services started!")

    try:
        await server.wait_for_termination()
    except (SystemExit, asyncio.exceptions.CancelledError):
        logger.info("Shutting down...")
        await server.stop(1)


if __name__ == "__main__":
    asyncio.run(main())  

