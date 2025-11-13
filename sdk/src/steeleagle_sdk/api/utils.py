import grpc
from typing import Any, Optional, Iterable, Tuple
from collections.abc import AsyncIterator, Callable
from google.protobuf.timestamp_pb2 import Timestamp
from .datatypes.common import Response
import logging
logger = logging.getLogger(__name__)

def now_ts() -> Timestamp:
    ts = Timestamp()
    ts.GetCurrentTime()
    return ts


def _grpc_code_int(code_obj: Any) -> int:
    """
    Make grpc.StatusCode value robust across versions:
    sometimes .value is int, sometimes it's a 1-tuple.
    """
    val = getattr(code_obj, "value", 0)
    if isinstance(val, tuple) and val:
        return int(val[0])
    return int(val)


def error_to_api_response(error: grpc.aio.AioRpcError) -> Response:
    """
    Map gRPC error codes (usually 0..16) to your API status space (+2 offset).
    """
    ts = now_ts()
    code_int = _grpc_code_int(error.code())
    return Response(
        status=code_int + 2,
        response_string=error.details(),
        timestamp=ts,
    )


def _default_metadata(md: Optional[Iterable[Tuple[str, str]]]) -> Tuple[Tuple[str, str], ...]:
    return tuple(md) if md is not None else (("identity", "internal"),)


async def run_unary(
    method_coro: Callable[..., Any],
    request_pb: Any,
    metadata: Optional[Iterable[Tuple[str, str]]] = None,
    timeout: Optional[float] = None,
) -> Response:
    """
    Runs a unary RPC and returns the protobuf Response directly.
    """
    ts = now_ts()
    request_pb.request.timestamp.CopyFrom(ts)

    md = _default_metadata(metadata)
    try:
        resp_pb = await method_coro(request_pb, metadata=md, timeout=timeout)
        return resp_pb  # expected to be common.Response
    except grpc.aio.AioRpcError as e:
        return error_to_api_response(e)


async def run_streaming(
    method_coro: Callable[..., Any],
    request_pb: Any,
    metadata: Optional[Iterable[Tuple[str, str]]] = None,
    timeout: Optional[float] = None,
) -> AsyncIterator[Response]:
    """
    Runs a streaming RPC and yields each Response as it arrives.
    """
    ts = now_ts()
    request_pb.request.timestamp.CopyFrom(ts)

    md = _default_metadata(metadata)
    call = None
    try:
        call = method_coro(request_pb, metadata=md, timeout=timeout)
        async for msg in call:
            yield msg
    except grpc.aio.AioRpcError as e:
        # Surface the error as a single terminal Response
        yield error_to_api_response(e)
    finally:
        # Best-effort cleanup if the stream is still open
        try:
            if call is not None:
                await call.cancel()
        except Exception:
            pass
