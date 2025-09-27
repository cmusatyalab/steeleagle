import grpc
from typing import Any, Tuple
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
def normalize(value: Any) -> Any:
    '''
    Normalize dataclasses/Enums/collections →  plain types for ParseDict.
    '''
    if isinstance(value, Enum):
        return int(value.value)  # ParseDict accepts Enum numbers
    if is_dataclass(value):
        return {k: normalize(v) for k, v in dc_asdict(value).items()}
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    return value

def payload_from_action(action: Any) -> dict:
    '''
    Extract action attributes as a dict, excluding any in `exclude`.
    '''
    ann = getattr(action, "__annotations__", {}) or {}
    raw = {
        k: getattr(action, k)
        for k in ann.keys()
        if hasattr(action, k) and getattr(action, k) is not None
    }
    return normalize(raw)

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
