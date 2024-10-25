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

    if socket_op == SocketOperation.CONNECT:
        logger.info(f"Connecting socket to {addr=}")
        socket.connect(addr)
    elif socket_op == SocketOperation.BIND:
        logger.info(f"Binding socket to {addr=}")
        socket.bind(addr)
    else:
        logger.fatal("Invalid socket operation")
        quit()

    logger.info(logger_message)
