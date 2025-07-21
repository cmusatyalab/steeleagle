# Protocol imports
from util.config import query_config
from python_bindings import common_pb2 as common_proto

async def unary_unary_request(rpc, context, request, logger):
    '''
    Makes a Unary->Unary request given an RPC functor and a
    request object.
    '''
    try:
        logger.log_proto(request)
        response = await rpc(request)
        logger.log_proto(response)
        return response
    except Exception as e:
        logger.error(f"RPC Exception occured, reason: {e}")
        context.set_code(grpc.StatusCode.INTERNAL)
        context.set_details(f"Encountered internal error, {e}")
        context.abort()

async def unary_stream_request(rpc, context, request, logger):
    '''
    Makes a Unary->Stream request given an RPC functor and a
    request object.
    '''
    try:
        logger.log_proto(request)
        async for response in rpc(request):
            logger.log_proto(response)
            yield response
    except Exception as e:
        logger.error(f"RPC Exception occured, reason: {e}")
        context.set_code(grpc.StatusCode.INTERNAL)
        context.set_details(f"Encountered internal error, {e}")
        context.abort()

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
