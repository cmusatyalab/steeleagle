---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# remote_service_pb2_grpc

Client and server classes corresponding to protobuf-defined services.

---

## <><code style={{color: '#13a6cf'}}>func</code></> add_RemoteServicer_to_server

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def add_RemoteServicer_to_server(servicer, server):
    rpc_method_handlers = {'RemoteControl': grpc.unary_unary_rpc_method_handler(servicer.RemoteControl, request_deserializer=services_dot_remote__service__pb2.RemoteControlRequest.FromString, response_serializer=services_dot_remote__service__pb2.RemoteControlResponse.SerializeToString)}
    generic_handler = grpc.method_handlers_generic_handler('steeleagle.protocol.services.remote_service.Remote', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('steeleagle.protocol.services.remote_service.Remote', rpc_method_handlers)

```
</details>

---
## <><code style={{color: '#b52ee6'}}>class</code></> RemoteStub

*Inherits from: <code>object</code>*

Used to control a vehicle remotely over ZeroMQ
Not implemented as a gRPC service!



<details>
<summary>View Source</summary>
```python
class RemoteStub(object):
    """
    Used to control a vehicle remotely over ZeroMQ
    Not implemented as a gRPC service!
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.RemoteControl = channel.unary_unary('/steeleagle.protocol.services.remote_service.Remote/RemoteControl', request_serializer=services_dot_remote__service__pb2.RemoteControlRequest.SerializeToString, response_deserializer=services_dot_remote__service__pb2.RemoteControlResponse.FromString, _registered_method=True)

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> RemoteServicer

*Inherits from: <code>object</code>*

Used to control a vehicle remotely over ZeroMQ
Not implemented as a gRPC service!


### <><code style={{color: '#10c45b'}}>method</code></> RemoteControl

_Call Type: normal_


Sends a request to one of the core services (Control, Mission, etc.)

<details>
<summary>View Source</summary>
```python
class RemoteServicer(object):
    """
    Used to control a vehicle remotely over ZeroMQ
    Not implemented as a gRPC service!
    """

    def RemoteControl(self, request, context):
        """Sends a request to one of the core services (Control, Mission, etc.)
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> Remote

*Inherits from: <code>object</code>*

Used to control a vehicle remotely over ZeroMQ
Not implemented as a gRPC service!


### <><code style={{color: '#10c45b'}}>method</code></> RemoteControl

_Call Type: normal_


<details>
<summary>View Source</summary>
```python
class Remote(object):
    """
    Used to control a vehicle remotely over ZeroMQ
    Not implemented as a gRPC service!
    """

    @staticmethod
    def RemoteControl(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.remote_service.Remote/RemoteControl', services_dot_remote__service__pb2.RemoteControlRequest.SerializeToString, services_dot_remote__service__pb2.RemoteControlResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)
```
</details>


---
