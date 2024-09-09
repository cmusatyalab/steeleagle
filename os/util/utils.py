import os
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def setup_socket(socket, socket_type, port_num, logger_message, host_addr="*"):
    # Get port number from environment variables
    port = os.environ.get(port_num, "")
    
    if not port:
        logger.error(f'Cannot get {port_num} from system')
        quit()

    # Construct the address
    addr = f'tcp://{host_addr}:{port}'
    
    logger.info(f"addr: {addr}")
    
    if socket_type == 'connect':
        socket.connect(addr)
    elif socket_type == 'bind':
        socket.bind(addr)

    logger.info(logger_message)
