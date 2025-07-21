from enum import Enum
import zmq
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
    indices = access_token.split('.')
    # Automatically get the associated endpoint
    host = query_config(access_token)
    if not isinstance(host, str):
        raise ValueError("Access token did not yield expected type string")
    addr = f'tcp://{host}'
    if sock_opt == SocketOperation.CONNECT:
        socket.connect(addr)
    elif sock_opt == SocketOperation.BIND:
        socket.bind(addr)
    else:
        raise ValueError("Invalid socket operation")
