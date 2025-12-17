from enum import Enum
# Utility import
from util.config import query_config

class SocketOperation(Enum):
    BIND = 0
    CONNECT = 1

def setup_zmq_socket(socket, access_token, sock_opt):
    '''
    Socket setup helper function. Sets up a socket using a 
    provided access token.
    '''
    # Automatically get the associated endpoint
    host = query_config(access_token)
    if not isinstance(host, str):
        raise ValueError("Access token did not yield expected type string")
    if sock_opt == SocketOperation.CONNECT:
        if 'unix' in host:
            addr = host.replace('unix', 'ipc')
        else:
            addr = f'tcp://{host}'
        socket.connect(addr)
    elif sock_opt == SocketOperation.BIND:
        if 'unix' in host:
            addr = host.replace('unix', 'ipc')
        else:
            port = host.split(':')[-1]
            addr = f'tcp://*:{port}' 
        socket.bind(addr)
    else:
        raise ValueError("Invalid socket operation")
