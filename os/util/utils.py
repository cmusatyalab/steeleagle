from enum import Enum
import os
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class SocketOperation(Enum):
    BIND = 1
    CONNECT = 2

def setup_socket(socket, socket_op, port_num, logger_message, host_addr="*"):
    # Get port number from environment variables
    port = os.environ.get(port_num, "")

    if not port:
        logger.fatal(f'Cannot get {port_num} from system')
        quit()

    # Construct the address
    addr = f'tcp://{host_addr}:{port}'

    logger.info(f"Setting up socket at {addr=}")

    if socket_op == SocketOperation.CONNECT:
        socket.connect(addr)
    elif socket_op == SocketOperation.BIND:
        socket.bind(addr)
    else:
        logger.fatal("Invalid socket operation")
        quit()

    logger.info(logger_message)
