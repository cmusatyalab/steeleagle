---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# flight_log_service_pb2_grpc

Client and server classes corresponding to protobuf-defined services.

---

## <><code style={{color: '#13a6cf'}}>func</code></> add_FlightLogServicer_to_server

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def add_FlightLogServicer_to_server(servicer, server):
    rpc_method_handlers = {'Log': grpc.unary_unary_rpc_method_handler(servicer.Log, request_deserializer=services_dot_flight__log__service__pb2.LogRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'LogProto': grpc.unary_unary_rpc_method_handler(servicer.LogProto, request_deserializer=services_dot_flight__log__service__pb2.LogProtoRequest.FromString, response_serializer=common__pb2.Response.SerializeToString)}
    generic_handler = grpc.method_handlers_generic_handler('steeleagle.protocol.services.flight_log_service.FlightLog', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('steeleagle.protocol.services.flight_log_service.FlightLog', rpc_method_handlers)

```
</details>

---
## <><code style={{color: '#b52ee6'}}>class</code></> FlightLogStub

*Inherits from: <code>object</code>*

Used to log to a flight log.

This service is hosted by a logger instance and is responsible
for writing all system logs to an MCAP file for mission playback.



<details>
<summary>View Source</summary>
```python
class FlightLogStub(object):
    """
    Used to log to a flight log.

    This service is hosted by a logger instance and is responsible
    for writing all system logs to an MCAP file for mission playback.
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Log = channel.unary_unary('/steeleagle.protocol.services.flight_log_service.FlightLog/Log', request_serializer=services_dot_flight__log__service__pb2.LogRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.LogProto = channel.unary_unary('/steeleagle.protocol.services.flight_log_service.FlightLog/LogProto', request_serializer=services_dot_flight__log__service__pb2.LogProtoRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> FlightLogServicer

*Inherits from: <code>object</code>*

Used to log to a flight log.

This service is hosted by a logger instance and is responsible
for writing all system logs to an MCAP file for mission playback.


### <><code style={{color: '#10c45b'}}>method</code></> Log

_Call Type: normal_


Basic log endpoint.

Behaves identically to most log endpoints, but writes the data to
an MCAP file instead of the console.
### <><code style={{color: '#10c45b'}}>method</code></> LogProto

_Call Type: normal_


Protobuf log endpoint.

Accepts Protobuf Request/Response types, and writes the data to
an MCAP file. Useful for playback of gRPC calls.

<details>
<summary>View Source</summary>
```python
class FlightLogServicer(object):
    """
    Used to log to a flight log.

    This service is hosted by a logger instance and is responsible
    for writing all system logs to an MCAP file for mission playback.
    """

    def Log(self, request, context):
        """
        Basic log endpoint.

        Behaves identically to most log endpoints, but writes the data to
        an MCAP file instead of the console.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def LogProto(self, request, context):
        """
        Protobuf log endpoint.

        Accepts Protobuf Request/Response types, and writes the data to
        an MCAP file. Useful for playback of gRPC calls.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> FlightLog

*Inherits from: <code>object</code>*

Used to log to a flight log.

This service is hosted by a logger instance and is responsible
for writing all system logs to an MCAP file for mission playback.


### <><code style={{color: '#10c45b'}}>method</code></> Log

_Call Type: normal_

### <><code style={{color: '#10c45b'}}>method</code></> LogProto

_Call Type: normal_


<details>
<summary>View Source</summary>
```python
class FlightLog(object):
    """
    Used to log to a flight log.

    This service is hosted by a logger instance and is responsible
    for writing all system logs to an MCAP file for mission playback.
    """

    @staticmethod
    def Log(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.flight_log_service.FlightLog/Log', services_dot_flight__log__service__pb2.LogRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def LogProto(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.flight_log_service.FlightLog/LogProto', services_dot_flight__log__service__pb2.LogProtoRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)
```
</details>


---
