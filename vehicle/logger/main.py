import asyncio
import grpc
from concurrent import futures
from pathlib import Path
from datetime import datetime, timezone
# Utility import
from util.config import query_config
from util.cleanup import register_cleanup_handler
register_cleanup_handler() # Cleanup handler for SIGTERM
# Protocol import
from steeleagle_sdk.protocol.services import flight_log_service_pb2_grpc
# Service import
from flight_log_service import FlightLogService

async def main():
    # Get the file path
    filepath = Path(__file__).parent / 'logs'
    if query_config('logging.custom_filename') != '':
        filepath = filepath / query_config('logging.custom_filename')
    else:
        date_time = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H:%M:%S")
        name = query_config('vehicle.name')
        filename = name + '_' + date_time + '.mcap'
        filepath = filepath / filename

    # Create the log server
    server = grpc.aio.server(
            migration_thread_pool=futures.ThreadPoolExecutor(max_workers=10)
            )
    # Create and assign the log service to the server
    log_server = FlightLogService(str(filepath))
    flight_log_service_pb2_grpc.add_FlightLogServicer_to_server(log_server, server)
    # Add log channel to server
    server.add_insecure_port(query_config('internal.services.flight_log'))
    
    await server.start()

    try:
        await server.wait_for_termination()
    except (SystemExit, asyncio.exceptions.CancelledError):
        await server.stop(1)
    finally:
        log_server.cleanup()
        
if __name__ == "__main__":
    asyncio.run(main())
