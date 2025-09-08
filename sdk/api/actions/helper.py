
from google.protobuf.timestamp_pb2 import Timestamp as ProtoTimestamp
from typing import Any
from enum import Enum
from dataclasses import is_dataclass, asdict as dc_asdict
from typing import Any, Tuple
from bindings.python.services import control_service_pb2 as ctrl_pb

from api.messages.common import (
    Response as CommonResponse,
    ResponseStatus
)

# =============================================================================
# Shared helpers
# =============================================================================

def _stamp_now(req_pb: Any) -> None:
    """set timestamp to 'now'."""
    ts = ProtoTimestamp()
    ts.GetCurrentTime()
    req_pb.request.timestamp.CopyFrom(ts)


def _norm(value: Any) -> Any:
    """Normalize dataclasses/Enums/collections → plain types for ParseDict."""
    if isinstance(value, Enum):
        return int(value.value)  # ParseDict accepts enum numbers
    if is_dataclass(value):
        return {k: _norm(v) for k, v in dc_asdict(value).items()}
    if isinstance(value, dict):
        return {k: _norm(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_norm(v) for v in value]
    return value


def _payload_from_action(action: Any, *, exclude: Tuple[str, ...] = ()) -> dict:
    """
    Build a dict from the action’s annotated fields (minus internal flags).
    Generator-friendly: you don’t need to list fields manually per RPC.
    """
    ann = getattr(action, "__annotations__", {}) or {}
    raw = {
        k: getattr(action, k)
        for k in ann.keys()
        if k not in exclude and hasattr(action, k) and getattr(action, k) is not None
    }
    return _norm(raw)


def _to_common_response(resp_pb: Any) -> CommonResponse:
    """
    Convert any <...Response> proto (with .response holding common.Response)
    into your types.common.Response (CommonResponse).
    """
    inner = getattr(resp_pb, "response", None)
    status = ResponseStatus(getattr(inner, "status"))
    msg = getattr(inner, "response_string", "") or getattr(inner, "message", "")
    ts = TypesTimestamp(  # type: ignore
                seconds=inner.timestamp.seconds,
                nanos=inner.timestamp.nanos,
            )

    return CommonResponse(status=status, response_string=msg, timestamp=ts)


async def _run_unary(method_coro, req_pb, *, metadata=None, timeout=None) -> CommonResponse:
    """Unary RPC -> CommonResponse."""
    _stamp_now(req_pb)
    resp_pb = await method_coro(req_pb, metadata=metadata, timeout=timeout)
    return _to_common_response(resp_pb)


async def _run_streaming(method_coro, req_pb, *, metadata=None, timeout=None) -> CommonResponse:
    """Server-streaming RPC -> drain and return last response as CommonResponse."""
    _stamp_now(req_pb)
    call = method_coro(req_pb, metadata=metadata, timeout=timeout)
    last = None
    async for msg in call:
        last = msg
    if last is None:
        # synthesize an empty-shaped response of the right type if stream was empty
        empty = ctrl_pb.TakeOffResponse()
        return _to_common_response(empty)
    return _to_common_response(last)


