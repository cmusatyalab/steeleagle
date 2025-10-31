from Anafi.Anafi import Anafi
import asyncio
from asyncio import futures
import grpc
import logging

# Utility imports
from ...vehicle.util.log import setup_logging
from ...vehicle.util.config import query_config
from ...vehicle.util.cleanup import register_cleanup_handler

# Protocol imports
from proto_build.services import control_service_pb2_grpc

setup_logging()
logger = logging.getLogger("Parrot/main")

async def main():
    register_cleanup_handler()
    server = grpc.aio.server(
        migration_thread_pool=futures.ThreadPoolExecutor(max_workers=10)
    )
    control_service_pb2_grpc.add_ControlServicer_to_server(
        Anafi("Anafi"), server
    )
    server.add_insecure_port(query_config("internal.services.driver"))
    await server.start()
    logger.info("Services started!")

    try:
        await server.wait_for_termination()
    except (SystemExit, asyncio.exceptions.CancelledError):
        logger.info("Shutting down...")
        await server.stop(1)


if __name__ == "__main__":
    asyncio.run(main())  

