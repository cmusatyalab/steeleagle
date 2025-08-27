import logging
import os
import shutil
from datetime import datetime
from enum import Enum

import pytz
import yaml
import zmq
import zmq.asyncio

logger = logging.getLogger(__name__)


class SocketOperation(Enum):
    BIND = 1
    CONNECT = 2


def setup_socket(socket, socket_op, access_token=None, port_num=None, host_addr="*"):
    """
    Socket setup helper function. Sets up a socket and returns it to the caller,
    either using a provided port number and host address, or using a access token.
    """
    if access_token:
        addr = query_config(access_token)
    elif isinstance(port_num, int):
        addr = f"tcp://{host_addr}:{port_num}"
    else:
        raise ValueError("Expected port number to be an int or a provided access token")

    if socket_op == SocketOperation.CONNECT:
        logger.info(f"Connecting socket to {addr}")
        socket.connect(addr)
    elif socket_op == SocketOperation.BIND:
        logger.info(f"Binding socket to {addr}")
        socket.bind(addr)
    else:
        raise ValueError("Invalid socket operation")


async def lazy_pirate_request(
    socket, payload, ctx, server_endpoint, retries=3, timeout=2500
):
    """
    Executes a lazy pirate request for client-side reliability. This is discussed
    in the ZeroMQ docs. Visit https://zguide.zeromq.org/docs/chapter4/ to learn more.
    """
    if retries <= 0:
        raise ValueError(f"Retries must be positive; {retries=}")
    # Send payload
    socket.send(payload)

    retries_left = retries
    while retries_left is None or retries_left > 0:
        # Check if reply received within timeout
        poll_result = await socket.poll(timeout)
        if (poll_result & zmq.POLLIN) != 0:
            reply = await socket.recv()
            return (socket, reply)
        if retries_left is not None:
            retries_left -= 1
        logger.warning(f"Request timeout for {server_endpoint=}")

        # Close the socket and create a new one
        socket.setsockopt(zmq.LINGER, 0)
        socket.close()

        logger.info(f"Reconnecting to {server_endpoint=}...")
        socket = ctx.socket(zmq.REQ)
        socket.connect(server_endpoint)

        if retries_left == 0:
            logger.info(f"Server {server_endpoint} offline, abandoning")
            return (socket, None)

        logger.info(f"Resending payload to {server_endpoint=}...")
        socket.send(payload)


def query_config(access_token):
    """
    Allows for accessing the config using a plaintext access token.
    An access token indexes a specific socket name in the vehicle config.yaml.
    This must be formatted in a Pythonic module import format. For example, for
    the driver_to_hub telemetry socket under dataplane and hub, it would be
    requested using the id: hub.dataplane.driver_to_hub.telemetry.
    """
    config = import_config()
    indices = access_token.split(".")
    result = config
    for i in indices:
        if i not in result.keys():
            raise ValueError(f"Malformed access token: {access_token}")
        result = result[i]  # Access the corresponding field
    return result


def import_config():
    """
    Import configuration file from environment variable.
    """
    config_path = os.environ.get("CONFIG_PATH")
    with open(config_path) as file:
        config = yaml.safe_load(file)
        return config


def setup_logging(logger, access_token=None):
    logging_format = (
        "%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s"
    )
    logging_config = None
    if access_token is not None:
        logging_config = query_config(access_token)

    if logging_config is not None:
        logging.basicConfig(
            level=logging_config["log_level"], format=logging_format, force=True
        )
    else:
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logging.basicConfig(
            level=getattr(logging, log_level, logging.INFO), format=logging_format
        )
        return

    log_file = logging_config["log_file"]
    if log_file:
        backup_logs(log_file)
        file_handler = logging.FileHandler(log_file, mode="w")
        file_handler.setFormatter(logging.Formatter(logging_format))
        file_handler.setLevel(logging_config["log_level"])
        logging.getLogger().addHandler(file_handler)


def backup_logs(log_file):
    if os.path.exists(log_file):
        timestamp = datetime.now(pytz.timezone("America/New_York")).strftime(
            "%Y%m%d_%H%M%S"
        )
        backup_file = f"{log_file}.{timestamp}.bak"
        shutil.move(log_file, backup_file)
