from enum import Enum
import logging
import os
import yaml
import zmq
import zmq.asyncio

logger = logging.getLogger(__name__)

class SocketOperation(Enum):
    BIND = 1
    CONNECT = 2

def setup_socket(socket, socket_op, port_num, host_addr="*"):
    if not isinstance(port_num, int):
        raise ValueError("Expected port number to be an int")

    # Construct the address
    addr = f'tcp://{host_addr}:{port_num}'

    match socket_op:
        case SocketOperation.CONNECT:
            logger.info(f"Connecting socket to {addr=}")
            socket.connect(addr)
        case SocketOperation.BIND:
            logger.info(f"Binding socket to {addr=}")
            socket.bind(addr)
        case _:
            raise ValueError("Invalid socket operation")

async def lazy_pirate_request(socket, payload, ctx, server_endpoint, retries=3,
                              timeout=2500):
    if retries <= 0:
        raise ValueError(f"Retries must be positive; {retries=}")
    # Send payload
    socket.send(payload)

    retries_left = retries
    while retries_left == None or retries_left > 0:
        # Check if reply received within timeout
        poll_result = await socket.poll(timeout)
        if (poll_result & zmq.POLLIN) != 0:
            reply = await socket.recv()
            return (socket, reply)
        if retries_left != None:
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

def import_config(config_path):
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
        return config

