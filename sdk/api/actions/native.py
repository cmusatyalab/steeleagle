from google.protobuf.timestamp_pb2 import Timestamp as ProtoTimestamp
from typing import Any
from enum import Enum
from dataclasses import is_dataclass, asdict as dc_asdict
from typing import Any, Tuple
# API imports
from api.messages.response import Response as APIResponse, ResponseStatus

''' Native helper functions '''
def timestamp_now(request_pb: Any) -> None:
    '''
    Set timestamp of request to 'now'.
    '''
    ts = ProtoTimestamp()
    ts.GetCurrentTime()
    request_pb.request.timestamp.CopyFrom(ts)

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

def payload_from_action(action: Any, *, exclude: Tuple[str, ...] = ()) -> dict:
    '''
    Build a dict from the action’s annotated fields (minus internal flags).
    Generator-friendly: you don’t need to list fields manually per RPC.
    '''
    ann = getattr(action, "__annotations__", {}) or {}
    raw = {
        k: getattr(action, k)
        for k in ann.keys()
        if k not in exclude and hasattr(action, k) and getattr(action, k) is not None
    }
    return normalize(raw)

def to_api_response(resp_pb: Any) -> APIResponse:
    '''
    Convert any <...Response> proto (with .response holding common.Response)
    into a Pydantic types.common.Response (APIResponse).
    '''
    inner = getattr(resp_pb, "response", None)
    status = ResponseStatus(getattr(inner, "status"))
    msg = getattr(inner, "response_string", "") or getattr(inner, "message", "")
    ts = TypesTimestamp(  # type: ignore
                seconds=inner.timestamp.seconds,
                nanos=inner.timestamp.nanos,
            )

    return APIResponse(status=status, response_string=msg, timestamp=ts)

async def run_unary(method_coro, request_pb, *, metadata=None, timeout=None) -> APIResponse:
    '''
    Native unary RPC -> APIResponse.
    '''
    timestamp_now(request_pb)
    resp_pb = await method_coro(request_pb, metadata=metadata, timeout=timeout)
    return to_api_response(resp_pb)

async def run_streaming(method_coro, request_pb, *, metadata=None, timeout=None) -> APIResponse:
    '''
    Native server-streaming RPC -> drain and return last response as APIResponse.
    '''
    timestamp_now(request_pb)
    call = method_coro(request_pb, metadata=metadata, timeout=timeout)
    last = None
    async for msg in call: 
        last = msg # Guaranteed at least one response
    return to_api_response(last)
