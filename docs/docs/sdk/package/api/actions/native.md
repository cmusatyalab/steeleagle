---
toc_max_heading_level: 2
---
# native

---

## <><code style={{color: '#13a6cf'}}>func</code></> now_ts

Get the current time as a Google Protobuf Timestamp.

Returns the current time as a Google Protobuf Timestamp object.
This is useful for setting the timestamp field inside a Request
object.

### Returns

`Timestamp` <text>&#8212;</text> current timestamp as a Google Protobuf Timestamp object.

---
## <><code style={{color: '#13a6cf'}}>func</code></> payload_from_action

Get the payload of an Action object as JSON.

Returns a JSON-ified version of the input Action object. This
is usually used to translate from the Python API into the Protobuf
API for serialization over the wire.

### Arguments
**<><code style={{color: '#db2146'}}>arg</code></> action** (`Action`) <text>&#8212;</text> input Action to be JSON serialized.


### Returns

`dict` <text>&#8212;</text> JSON serialized version of the input action.

---
## <><code style={{color: '#13a6cf'}}>func</code></> error_to_api_response

Get the corresponding Python API Response for an error code.

Returns a Python API Response for a corresponding gRPC error code.
Allows transformation of gRPC exceptions into a unified Response.

### Arguments
**<><code style={{color: '#db2146'}}>arg</code></> error** (`grpc.aio.AioRpcError`) <text>&#8212;</text> input gRPC Exception object.


### Returns

`Response` <text>&#8212;</text> Python API Response object.

---
## <><code style={{color: '#13a6cf'}}>func</code></> run_unary

Runs a unary gRPC method and returns a Python API Response.

Runs a unary gRPC method, gets the response (or error), and translates
it into a Python API Response.

### Arguments
**<><code style={{color: '#db2146'}}>arg</code></> method_coro** (`Any`) <text>&#8212;</text> an awaitable stub coroutine `STUB.METHOD` e.g.
ControlStub.Connect.

**<><code style={{color: '#db2146'}}>arg</code></> request_pb** (`Any`) <text>&#8212;</text> Protobuf object input for the method coroutine.

**<><code style={{color: '#db2146'}}>arg</code></> metadata** (`Optional[list]`) <text>&#8212;</text> 
metadata object for gRPC. The metadata must include an `identity` 
parameter to access kernel services. An `identity` set to 
`internal` signals to the kernel that the RPC request originates
from an onboard client.

**<><code style={{color: '#db2146'}}>arg</code></> timeout** (`Optional[int]`) <text>&#8212;</text> timeout for the RPC request, `None` indicates 
no timeout.


---
## <><code style={{color: '#13a6cf'}}>func</code></> run_streaming

Runs a streaming gRPC method and returns a Python API Response.

Runs a streaming gRPC method, gets the response (or error), and translates
it into a Python API Response. This method will only return the _last_
response it receives from the RPC.

### Arguments
**<><code style={{color: '#db2146'}}>arg</code></> method_coro** (`Any`) <text>&#8212;</text> an async generator stub coroutine `STUB.METHOD` e.g.
ControlStub.TakeOff.

**<><code style={{color: '#db2146'}}>arg</code></> request_pb** (`Any`) <text>&#8212;</text> Protobuf object input for the method coroutine.

**<><code style={{color: '#db2146'}}>arg</code></> metadata** (`Optional[list]`) <text>&#8212;</text> metadata object for gRPC. The metadata 
must include an `identity` parameter to access kernel services. 
An `identity` set to `internal` signals to the kernel that the 
RPC request originates from an onboard client.

**<><code style={{color: '#db2146'}}>arg</code></> timeout** (`Optional[int]`) <text>&#8212;</text> timeout for the RPC request, `None` indicates 
no timeout. It is generally not recommended to add a timeout to a 
streaming method, since most have non-deterministic time of completion.


---
