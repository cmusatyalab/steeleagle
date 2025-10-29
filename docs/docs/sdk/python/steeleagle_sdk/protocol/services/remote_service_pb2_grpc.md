---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# remote_service_pb2_grpc

Client and server classes corresponding to protobuf-defined services.

---

## <><code class="docs-func">func</code></> add_RemoteServicer_to_server

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def add_RemoteServicer_to_server(servicer, server):
    rpc_method_handlers = {'Command': grpc.unary_stream_rpc_method_handler(servicer.Command, request_deserializer=services_dot_remote__service__pb2.CommandRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'CompileMission': grpc.unary_stream_rpc_method_handler(servicer.CompileMission, request_deserializer=services_dot_remote__service__pb2.CompileMissionRequest.FromString, response_serializer=services_dot_remote__service__pb2.CompileMissionResponse.SerializeToString)}
    generic_handler = grpc.method_handlers_generic_handler('steeleagle.protocol.services.remote_service.Remote', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('steeleagle.protocol.services.remote_service.Remote', rpc_method_handlers)

```
</details>

---
## <><code class="docs-class">class</code></> RemoteStub

*Inherits from: <code>object</code>*

Used to control a vehicle remotely over ZeroMQ, usually hosted
on the server



<details>
<summary>View Source</summary>
```python
class RemoteStub(object):
    """
    Used to control a vehicle remotely over ZeroMQ, usually hosted
    on the server
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Command = channel.unary_stream('/steeleagle.protocol.services.remote_service.Remote/Command', request_serializer=services_dot_remote__service__pb2.CommandRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.CompileMission = channel.unary_stream('/steeleagle.protocol.services.remote_service.Remote/CompileMission', request_serializer=services_dot_remote__service__pb2.CompileMissionRequest.SerializeToString, response_deserializer=services_dot_remote__service__pb2.CompileMissionResponse.FromString, _registered_method=True)

```
</details>


---
## <><code class="docs-class">class</code></> RemoteServicer

*Inherits from: <code>object</code>*

Used to control a vehicle remotely over ZeroMQ, usually hosted
on the server


### <><code class="docs-method">method</code></> Command

_Call Type: normal_


Sends a service request to a vehicle core service (Control, Mission, etc.)
over ZeroMQ and returns the response
### <><code class="docs-method">method</code></> CompileMission

_Call Type: normal_


Missing associated documentation comment in .proto file.

<details>
<summary>View Source</summary>
```python
class RemoteServicer(object):
    """
    Used to control a vehicle remotely over ZeroMQ, usually hosted
    on the server
    """

    def Command(self, request, context):
        """Sends a service request to a vehicle core service (Control, Mission, etc.)
        over ZeroMQ and returns the response
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def CompileMission(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

```
</details>


---
## <><code class="docs-class">class</code></> Remote

*Inherits from: <code>object</code>*

Used to control a vehicle remotely over ZeroMQ, usually hosted
on the server


### <><code class="docs-method">method</code></> Command

_Call Type: normal_

### <><code class="docs-method">method</code></> CompileMission

_Call Type: normal_


<details>
<summary>View Source</summary>
```python
class Remote(object):
    """
    Used to control a vehicle remotely over ZeroMQ, usually hosted
    on the server
    """

    @staticmethod
    def Command(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.remote_service.Remote/Command', services_dot_remote__service__pb2.CommandRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def CompileMission(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_stream(request, target, '/steeleagle.protocol.services.remote_service.Remote/CompileMission', services_dot_remote__service__pb2.CompileMissionRequest.SerializeToString, services_dot_remote__service__pb2.CompileMissionResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)
```
</details>


---
