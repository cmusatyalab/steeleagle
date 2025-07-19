from enum import Enum
import os
import zmq
import zmq.asyncio
from util.config import query_config

class SocketOperation(Enum):
    BIND = 0
    CONNECT = 1

def setup_socket(socket, socket_op, access_token=None, port_num=None, host_addr="*"):
    '''
    Socket setup helper function. Sets up a socket and returns it to the caller,
    either using a provided port number and host address, or using an access token.
    '''
    if access_token:
        indices = access_token.split('.')
        # Automatically get the associated endpoint
        host = query_config(f'{indices[0]}.{indices[1]}.{indices[2]}.endpoint')
        port = query_config(access_token)
        if not isinstance(port, int):
            raise ValueError("Access token did not yield expected type int")
        addr = f'tcp://{host}:{port}'
    elif isinstance(port_num, int):
        addr = f'tcp://{host_addr}:{port_num}'
    else:
        raise ValueError("Expected port number to be an int or a provided access token")

    if socket_op == SocketOperation.CONNECT:
        socket.connect(addr)
    elif socket_op == SocketOperation.BIND:
        socket.bind(addr)
    else:
        raise ValueError("Invalid socket operation")
