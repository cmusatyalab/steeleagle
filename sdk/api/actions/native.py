import grpc
from typing import Any, Tuple, Mapping
from enum import Enum
from dataclasses import is_dataclass, asdict as dc_asdict
# API imports
from ..datatypes.common import Response
from google.protobuf.timestamp_pb2 import Timestamp as ProtoTimestamp
import logging
logger = logging.getLogger(__name__)



def _now_ts() -> ProtoTimestamp:
    ts = ProtoTimestamp()
    ts.GetCurrentTime()
    return ts

''' Native helper functions '''
def payload_from_action(action: Any) -> dict:
    data = action.model_dump(exclude_none=True, by_alias=True, mode = "json")  # v2
    return data

def error_to_api_response(error: grpc.aio.AioRpcError) -> Response:
    ts = _now_ts()
    # Note: gRPC error codes start from 0, API Response codes start from 2
    return Response(status=error.code().value[0] + 2, response_string=error.details(), timestamp=ts)

async def run_unary(method_coro, request_pb, *, metadata=None, timeout=None) -> Response:
    '''
    Native unary RPC -> Response.
    '''
    ts = _now_ts()
    request_pb.request.timestamp.CopyFrom(ts)
    try:
        resp_pb = await method_coro(request_pb, metadata=metadata, timeout=timeout)
        return resp_pb
    except grpc.aio.AioRpcError as e:
        return error_to_api_response(e)

async def run_streaming(method_coro, request_pb, *, metadata=None, timeout=None) -> Response:
    '''
    Native server-streaming RPC -> drain and return last response as Response.
    '''
    ts = _now_ts()
    request_pb.request.timestamp.CopyFrom(ts)
    call = method_coro(request_pb, metadata=metadata, timeout=timeout)
    last = None
    try:
        async for msg in call:
            last = msg  # Guaranteed at least one response
        logger.info(f"Streaming response received: {last}")
        return last
    except grpc.aio.AioRpcError as e:
        return error_to_api_response(e)
