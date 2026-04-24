import argparse
import json
import asyncio
import logging
import sys
from concurrent import futures
from typing import Dict

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import grpc

# Protocol imports
from steeleagle_sdk.protocol.services import mission_service_pb2_grpc

from .mission_service import MissionService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("mission/main")


def load_config_from_toml(config_path: str) -> Dict:
    """Load drone configuration from a TOML file."""
    with open(config_path, "rb") as f:
        config = tomllib.load(f)
    return config.get("drone", {})


async def main(drone_config: Dict):
    """
    Start mission service for a single drone.

    Args:
        drone_config: Dict with drone configuration
    """
    name = drone_config["name"]
    address = {
        "vehicle": drone_config["kernel"],
        "telemetry": drone_config["telemetry"],
        "results": drone_config["results"],
    }
    mission_sock = drone_config["mission_sock"]

    # Define the server that will hold our services
    server = grpc.aio.server(
        migration_thread_pool=futures.ThreadPoolExecutor(max_workers=10)
    )

    # Create and assign the service to the server
    mission_service_pb2_grpc.add_MissionServicer_to_server(
        MissionService(name, address), server
    )

    # Add the mission socket
    server.add_insecure_port(mission_sock)

    # Start services
    await server.start()
    logger.info(f"[{name}] Mission service listening on {mission_sock}")
    logger.info(f"[{name}]   -> vehicle: {address['vehicle']}")
    logger.info(f"[{name}]   -> telemetry: {address['telemetry']}")
    logger.info(f"[{name}]   -> results: {address['results']}")

    try:
        await server.wait_for_termination()
    except (SystemExit, asyncio.exceptions.CancelledError):
        logger.info("Shutting down...")
        await server.stop(1)


def cli():
    parser = argparse.ArgumentParser(
        prog="Mission Service",
        description="Mission service for a SteelEagle drone",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Path to TOML config file with drone definition. "
             "Example: -c config.toml",
    )
    parser.add_argument(
        '-j',
        '--json',
        type=json.loads,
        default=None,
        help='Config in json format'
    )
    args = parser.parse_args()

    # Load drone config from file or use defaults
    if args.config:
        try:
            drone_config = load_config_from_toml(args.config)
            print(f"Loaded config for '{drone_config['name']}' from {args.config}")
        except Exception as e:
            print(f"Error loading config file {args.config}: {e}")
            sys.exit(1)
    elif args.json:
        drone_config = args.json
    else:
        # Default single drone configuration
        drone_config = {
            "name": "drone0",
            "kernel": "unix:///tmp/kernel.sock",
            "telemetry": "ipc:///tmp/driver_telem.sock",
            "results": "ipc:///tmp/results.sock",
            "mission_sock": "unix:///tmp/mission.sock",
        }

    asyncio.run(main(drone_config))


if __name__ == "__main__":
    cli()
