import inspect
# Protocol imports
from google.protobuf.timestamp_pb2 import Timestamp
from util.config import query_config
from python_bindings import common_pb2 as common_proto

async def async_unary_unary_request(rpc, request, logger=None):
    '''
    Makes an optionally logged async Unary->Unary request given an 
    RPC functor and a request object.
    '''
    try:
        if logger:
            logger.info_proto(request)
        response = await rpc(request)
        if logger:
            logger.info_proto(response)
        logger.info(str(response))
        return response
    except Exception as e:
        if logger:
            logger.error(f"Unary->Unary RPC Exception occured, reason: {e}")
        raise

async def async_unary_stream_request(rpc, request, logger=None):
    '''
    Makes an optionally logged async Unary->Stream request given an 
    RPC functor and a request object.
    '''
    try:
        if logger: 
            logger.info_proto(request)
        async for response in rpc(request):
            if logger:
                logger.info_proto(response)
            yield response
    except Exception as e:
        if logger:
            logger.error(f"Unary->Stream RPC Exception occured, reason: {e}")
        raise

def get_bind_addr(addr):
    '''
    Creates the gRPC server bind address for a provided address.
    '''
    port = addr.split(':')[-1]
    return f'[::]:{port}'

def generate_request():
    '''
    Generates a protobuf request object for an RPC given a
    sender ID.
    '''
    return common_proto.Request(
            timestamp=Timestamp().GetCurrentTime()
            )

def generate_response(resp_type, resp_string=""):
    '''
    Generates a protobuf response object for an RPC given a
    response type and optional response string.
    '''
    return common_proto.Response(
            status=resp_type,
            response_string=resp_string,
            timestamp=Timestamp().GetCurrentTime()
            )
