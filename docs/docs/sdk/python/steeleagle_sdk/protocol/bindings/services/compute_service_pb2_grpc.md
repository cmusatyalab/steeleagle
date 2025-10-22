---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# compute_service_pb2_grpc

Client and server classes corresponding to protobuf-defined services.

---

## <><code style={{color: '#13a6cf'}}>func</code></> add_ComputeServicer_to_server

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def add_ComputeServicer_to_server(servicer, server):
    rpc_method_handlers = {'GetAvailableDatasinks': grpc.unary_unary_rpc_method_handler(servicer.GetAvailableDatasinks, request_deserializer=services_dot_compute__service__pb2.GetAvailableDatasinksRequest.FromString, response_serializer=services_dot_compute__service__pb2.GetAvailableDatasinksResponse.SerializeToString), 'ConfigureDatasinks': grpc.unary_unary_rpc_method_handler(servicer.ConfigureDatasinks, request_deserializer=services_dot_compute__service__pb2.ConfigureDatasinksRequest.FromString, response_serializer=services_dot_compute__service__pb2.ConfigureDatasinksResponse.SerializeToString)}
    generic_handler = grpc.method_handlers_generic_handler('steeleagle.protocol.services.compute_service.Compute', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('steeleagle.protocol.services.compute_service.Compute', rpc_method_handlers)

```
</details>

---
## <><code style={{color: '#b52ee6'}}>class</code></> ComputeStub

*Inherits from: <code>object</code>*

Used to configure datasinks for sensor streams



<details>
<summary>View Source</summary>
```python
class ComputeStub(object):
    """
    Used to configure datasinks for sensor streams
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.GetAvailableDatasinks = channel.unary_unary('/steeleagle.protocol.services.compute_service.Compute/GetAvailableDatasinks', request_serializer=services_dot_compute__service__pb2.GetAvailableDatasinksRequest.SerializeToString, response_deserializer=services_dot_compute__service__pb2.GetAvailableDatasinksResponse.FromString, _registered_method=True)
        self.ConfigureDatasinks = channel.unary_unary('/steeleagle.protocol.services.compute_service.Compute/ConfigureDatasinks', request_serializer=services_dot_compute__service__pb2.ConfigureDatasinksRequest.SerializeToString, response_deserializer=services_dot_compute__service__pb2.ConfigureDatasinksResponse.FromString, _registered_method=True)

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> ComputeServicer

*Inherits from: <code>object</code>*

Used to configure datasinks for sensor streams


### <><code style={{color: '#10c45b'}}>method</code></> GetAvailableDatasinks

_Call Type: normal_


Get all available compute engines, both local and remote
### <><code style={{color: '#10c45b'}}>method</code></> ConfigureDatasinks

_Call Type: normal_


Configure compute preferences

<details>
<summary>View Source</summary>
```python
class ComputeServicer(object):
    """
    Used to configure datasinks for sensor streams
    """

    def GetAvailableDatasinks(self, request, context):
        """Get all available compute engines, both local and remote
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ConfigureDatasinks(self, request, context):
        """Configure compute preferences
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> Compute

*Inherits from: <code>object</code>*

Used to configure datasinks for sensor streams


### <><code style={{color: '#10c45b'}}>method</code></> GetAvailableDatasinks

_Call Type: normal_

### <><code style={{color: '#10c45b'}}>method</code></> ConfigureDatasinks

_Call Type: normal_


<details>
<summary>View Source</summary>
```python
class Compute(object):
    """
    Used to configure datasinks for sensor streams
    """

    @staticmethod
    def GetAvailableDatasinks(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.compute_service.Compute/GetAvailableDatasinks', services_dot_compute__service__pb2.GetAvailableDatasinksRequest.SerializeToString, services_dot_compute__service__pb2.GetAvailableDatasinksResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def ConfigureDatasinks(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.compute_service.Compute/ConfigureDatasinks', services_dot_compute__service__pb2.ConfigureDatasinksRequest.SerializeToString, services_dot_compute__service__pb2.ConfigureDatasinksResponse.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)
```
</details>


---
