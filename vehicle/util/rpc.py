import inspect
# Protocol imports
from google.protobuf.timestamp_pb2 import Timestamp
from util.config import query_config
from python_bindings import common_pb2 as common_proto

async def reflective_grpc_call(metadata, full_method_name, method_desc, request, classes, channel, timeout=3):
    '''
    Calls the provided gRPC method by invoking it directly on the channel.
    '''
    # Get the classes for request and response, needed to deserialize
    # and serialize messages from the channel correctly
    req_class, rep_class = classes

    if method_desc.server_streaming:
        # Server-streaming call
        call = channel.unary_stream(
            full_method_name,
            request_serializer=req_class.SerializeToString,
            response_deserializer=rep_class.FromString
        )
        responses = []
        # In this case, call responds with a wrapper that is an async
        # generator function
        try:
            async for resp in call(request, timeout=timeout, metadata=metadata):
                responses.append(resp)
            return responses[-1] # Just the last response is needed
        except:
            raise
    else:
        # Unary call
        call = channel.unary_unary(
            full_method_name,
            request_serializer=req_class.SerializeToString,
            response_deserializer=rep_class.FromString
        )
        try:
            return await call(request, timeout=timeout, metadata=metadata)
        except:
            raise

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
