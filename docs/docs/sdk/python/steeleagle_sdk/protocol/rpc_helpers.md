---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# rpc_helpers

---

## <><code style={{color: '#13a6cf'}}>func</code></> native_grpc_call

_Call Type: async_


Calls the provided gRPC method by invoking it directly on the channel.
<details>
<summary>View Source</summary>
```python
async def native_grpc_call(metadata, full_method_name, method_desc, request, classes, channel):
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
        async for resp in call(request, metadata=metadata):
            responses.append(resp)
        return responses[-1] # Just the last response is needed
    else:
        # Unary call
        call = channel.unary_unary(
            full_method_name,
            request_serializer=req_class.SerializeToString,
            response_deserializer=rep_class.FromString
        )
        return await call(request, metadata=metadata)

```
</details>

---
## <><code style={{color: '#13a6cf'}}>func</code></> generate_request

_Call Type: normal_


Generates a protobuf request object for an RPC given a
sender ID.
<details>
<summary>View Source</summary>
```python
def generate_request():
    '''
    Generates a protobuf request object for an RPC given a
    sender ID.
    '''
    return Request(
            timestamp=Timestamp().GetCurrentTime()
            )

```
</details>

---
## <><code style={{color: '#13a6cf'}}>func</code></> generate_response

_Call Type: normal_


Generates a protobuf response object for an RPC given a
response type and optional response string.
<details>
<summary>View Source</summary>
```python
def generate_response(resp_type, resp_string=""):
    '''
    Generates a protobuf response object for an RPC given a
    response type and optional response string.
    '''
    return Response(
            status=resp_type,
            response_string=resp_string,
            timestamp=Timestamp().GetCurrentTime()
            )

```
</details>

---
