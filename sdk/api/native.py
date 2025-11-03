import grpc
from typing import Any, Optional
# API imports
from google.protobuf.timestamp_pb2 import Timestamp

def now_ts() -> Timestamp:
    """Get the current time as a Google Protobuf Timestamp.
    
    Returns the current time as a Google Protobuf Timestamp object.
    This is useful for setting the timestamp field inside a Request
    object.

    Returns:
        Timestamp: current timestamp as a Google Protobuf Timestamp object.
    """
    ts = Timestamp()
    ts.GetCurrentTime()
    return ts

def error_to_api_response(error: grpc.aio.AioRpcError) -> Response:
    """Get the corresponding Python API Response for an error code.

    Returns a Python API Response for a corresponding gRPC error code.
    Allows transformation of gRPC exceptions into a unified Response.

    Args:
        error (grpc.aio.AioRpcError): input gRPC Exception object.

    Returns:
        Response: Python API Response object.
    """
    ts = now_ts()
    # Note: gRPC error codes start from 0, API Response codes start from 2
    return Response(status=error.code().value[0] + 2, response_string=error.details(), timestamp=ts)

async def run_unary(method_coro: Any, request_pb: Any, metadata: Optional[list]=[('identity', 'internal')], timeout: Optional[int]=None) -> Response:
    """Runs a unary gRPC method and returns a Python API Response.

    Runs a unary gRPC method, gets the response (or error), and translates
    it into a Python API Response.

    Args:
        method_coro (Any): an awaitable stub coroutine `STUB.METHOD` e.g.
            ControlStub.Connect.
        request_pb (Any): Protobuf object input for the method coroutine.
        metadata (Optional[list]): 
            metadata object for gRPC. The metadata must include an `identity` 
            parameter to access kernel services. An `identity` set to 
            `internal` signals to the kernel that the RPC request originates
            from an onboard client.
        timeout (Optional[int]): timeout for the RPC request, `None` indicates 
            no timeout.
    """
    ts = now_ts()
    request_pb.request.timestamp.CopyFrom(ts)
    try:
        resp_pb = await method_coro(request_pb, metadata=metadata, timeout=timeout)
        return resp_pb
    except grpc.aio.AioRpcError as e:
        return error_to_api_response(e)

async def run_streaming(method_coro: Any, request_pb: Any, metadata: Optional[list]=[('identity', 'internal')], timeout: Optional[int]=None) -> Response:
    """Runs a streaming gRPC method and returns a Python API Response.

    Runs a streaming gRPC method, gets the response (or error), and translates
    it into a Python API Response. This method will only return the _last_
    response it receives from the RPC.

    Args:
        method_coro (Any): an async generator stub coroutine `STUB.METHOD` e.g.
            ControlStub.TakeOff.
        request_pb (Any): Protobuf object input for the method coroutine.
        metadata (Optional[list]): metadata object for gRPC. The metadata 
            must include an `identity` parameter to access kernel services. 
            An `identity` set to `internal` signals to the kernel that the 
            RPC request originates from an onboard client.
        timeout (Optional[int]): timeout for the RPC request, `None` indicates 
            no timeout. It is generally not recommended to add a timeout to a 
            streaming method, since most have non-deterministic time of completion.
    """
    ts = now_ts()
    request_pb.request.timestamp.CopyFrom(ts)
    call = method_coro(request_pb, metadata=metadata, timeout=timeout)
    last = None
    try:
        async for msg in call:
            last = msg  # Guaranteed at least one response
        return last
    except grpc.aio.AioRpcError as e:
        return error_to_api_response(e)
