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

def setup_socket(socket, socket_op, access_token=None, port_num=None, host_addr="*"):
    '''
    Socket setup helper function. Sets up a socket and returns it to the caller,
    either using a provided port number and host address, or using a access token.
    '''
    if access_token:
        indices = access_token.split('.')
        host = query_config(f'{indices[0]}.{indices[1]}.endpoint') 
        port = query_config(access_token)
        if not isinstance(port, int):
            raise ValueError("Access token did not yield expected type int")
        addr = f'tcp://{host}:{port}'
    elif isinstance(port_num, int):
        addr = f'tcp://{host_addr}:{port_num}'
    else
        raise ValueError("Expected port number to be an int or a provided access token")

    if socket_op == SocketOperation.CONNECT:
        logger.info(f"Connecting socket to {addr}")
        socket.connect(addr)
    elif socket_op == SocketOperation.BIND:
        logger.info(f"Binding socket to {addr}")
        socket.bind(addr)
    else:
        raise ValueError("Invalid socket operation")

async def lazy_pirate_request(socket, payload, ctx, server_endpoint, retries=3,
                              timeout=2500):
    '''
    Executes a lazy pirate request for client-side reliability. This is discussed
    in the ZeroMQ docs. Visit https://zguide.zeromq.org/docs/chapter4/ to learn more.
    '''
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

def query_config(access_token)
    '''
    Allows for accessing the config using a plaintext access token.
    An access token indexes a specific socket name in the vehicle config.yaml.
    This must be formatted in a Pythonic module import format. For example, for
    the driver_to_hub telemetry socket under dataplane and hub, it would be 
    requested using the id: hub.dataplane.driver_to_hub.telemetry.
    '''
    config = import_config()
    indices = access_token.split('.')
    result = config
    for i in indices:
        if i not in port.keys():
            raise ValueError("Malformed access token")
        result = result[i] # Access the corresponding field
    return result

def import_config():
    '''
    Import configuration file from environment variable.
    '''
    config_path = os.environ.get('CONFIG_PATH')
    with open(config_path, 'r') as file:
        config = yaml.safe_load(file)
        return config

def setup_logging(logger, logging_config):
    logging_format = "%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s"
    
    if logging_config is not None:
        logging.basicConfig(level=logging_config.get('log_level', logging.INFO), format=logging_format)
    else:
        logging.basicConfig(level=logging.INFO, format=logging_format)

    log_file = logging_config.get('log_file')
    if log_file is not None:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(logging_format))
        logger.addHandler(file_handler)
