---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# native

---

## <><code class="docs-func">func</code></> now_ts

_Call Type: normal_


Get the current time as a Google Protobuf Timestamp.

Returns the current time as a Google Protobuf Timestamp object.
This is useful for setting the timestamp field inside a Request
object.

### Returns

<code>google.protobuf.timestamp_pb2.Timestamp</code> <text>&#8212;</text> current timestamp as a Google Protobuf Timestamp object.
<details>
<summary>View Source</summary>
```python
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

```
</details>

---
## <><code class="docs-func">func</code></> payload_from_action

_Call Type: normal_


Get the payload of an Action object as JSON.

Returns a JSON-ified version of the input Action object. This
is usually used to translate from the Python API into the Protobuf
API for serialization over the wire.

### Arguments
**<><code class="docs-arg">arg</code></>&nbsp;&nbsp;action**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/base#class-action">Action</Link></code>) <text>&#8212;</text> input Action to be JSON serialized.


### Returns

<code>dict</code> <text>&#8212;</text> JSON serialized version of the input action.
<details>
<summary>View Source</summary>
```python
def payload_from_action(action: Action) -> dict:
    """Get the payload of an Action object as JSON.

    Returns a JSON-ified version of the input Action object. This
    is usually used to translate from the Python API into the Protobuf
    API for serialization over the wire.

    Args:
        action (Action): input Action to be JSON serialized.

    Returns:
        dict: JSON serialized version of the input action.
    """
    data = action.model_dump(exclude_none=True, by_alias=True, mode = "json")  # v2
    return data

```
</details>

---
## <><code class="docs-func">func</code></> error_to_api_response

_Call Type: normal_


Get the corresponding Python API Response for an error code.

Returns a Python API Response for a corresponding gRPC error code.
Allows transformation of gRPC exceptions into a unified Response.

### Arguments
**<><code class="docs-arg">arg</code></>&nbsp;&nbsp;error**&nbsp;&nbsp;(<code>grpc.aio.AioRpcError</code>) <text>&#8212;</text> input gRPC Exception object.


### Returns

<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/common#class-response">Response</Link></code> <text>&#8212;</text> Python API Response object.
<details>
<summary>View Source</summary>
```python
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

```
</details>

---
## <><code class="docs-func">func</code></> run_unary

_Call Type: async_


Runs a unary gRPC method and returns a Python API Response.

Runs a unary gRPC method, gets the response (or error), and translates
it into a Python API Response.

### Arguments
**<><code class="docs-arg">arg</code></>&nbsp;&nbsp;method_coro**&nbsp;&nbsp;(<code>typing.Any</code>) <text>&#8212;</text> an awaitable stub coroutine `STUB.METHOD` e.g.
ControlStub.Connect.

**<><code class="docs-arg">arg</code></>&nbsp;&nbsp;request_pb**&nbsp;&nbsp;(<code>typing.Any</code>) <text>&#8212;</text> Protobuf object input for the method coroutine.

**<><code class="docs-arg">arg</code></>&nbsp;&nbsp;metadata**&nbsp;&nbsp;(<code>Optional[list]</code>) <text>&#8212;</text> 
metadata object for gRPC. The metadata must include an `identity` 
parameter to access kernel services. An `identity` set to 
`internal` signals to the kernel that the RPC request originates
from an onboard client.

**<><code class="docs-arg">arg</code></>&nbsp;&nbsp;timeout**&nbsp;&nbsp;(<code>Optional[int]</code>) <text>&#8212;</text> timeout for the RPC request, `None` indicates 
no timeout.

<details>
<summary>View Source</summary>
```python
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

```
</details>

---
## <><code class="docs-func">func</code></> run_streaming

_Call Type: async_


Runs a streaming gRPC method and returns a Python API Response.

Runs a streaming gRPC method, gets the response (or error), and translates
it into a Python API Response. This method will only return the _last_
response it receives from the RPC.

### Arguments
**<><code class="docs-arg">arg</code></>&nbsp;&nbsp;method_coro**&nbsp;&nbsp;(<code>typing.Any</code>) <text>&#8212;</text> an async generator stub coroutine `STUB.METHOD` e.g.
ControlStub.TakeOff.

**<><code class="docs-arg">arg</code></>&nbsp;&nbsp;request_pb**&nbsp;&nbsp;(<code>typing.Any</code>) <text>&#8212;</text> Protobuf object input for the method coroutine.

**<><code class="docs-arg">arg</code></>&nbsp;&nbsp;metadata**&nbsp;&nbsp;(<code>Optional[list]</code>) <text>&#8212;</text> metadata object for gRPC. The metadata 
must include an `identity` parameter to access kernel services. 
An `identity` set to `internal` signals to the kernel that the 
RPC request originates from an onboard client.

**<><code class="docs-arg">arg</code></>&nbsp;&nbsp;timeout**&nbsp;&nbsp;(<code>Optional[int]</code>) <text>&#8212;</text> timeout for the RPC request, `None` indicates 
no timeout. It is generally not recommended to add a timeout to a 
streaming method, since most have non-deterministic time of completion.

<details>
<summary>View Source</summary>
```python
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

```
</details>

---
