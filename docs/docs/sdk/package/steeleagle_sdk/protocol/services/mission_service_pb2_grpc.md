---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';

# mission_service_pb2_grpc

Client and server classes corresponding to protobuf-defined services.

---

## <><code style={{color: '#13a6cf'}}>func</code></> add_MissionServicer_to_server

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def add_MissionServicer_to_server(servicer, server):
    rpc_method_handlers = {'Upload': grpc.unary_unary_rpc_method_handler(servicer.Upload, request_deserializer=services_dot_mission__service__pb2.UploadRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'Start': grpc.unary_unary_rpc_method_handler(servicer.Start, request_deserializer=services_dot_mission__service__pb2.StartRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'Stop': grpc.unary_unary_rpc_method_handler(servicer.Stop, request_deserializer=services_dot_mission__service__pb2.StopRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'Notify': grpc.unary_unary_rpc_method_handler(servicer.Notify, request_deserializer=services_dot_mission__service__pb2.NotifyRequest.FromString, response_serializer=common__pb2.Response.SerializeToString), 'ConfigureTelemetryStream': grpc.unary_unary_rpc_method_handler(servicer.ConfigureTelemetryStream, request_deserializer=services_dot_mission__service__pb2.ConfigureTelemetryStreamRequest.FromString, response_serializer=common__pb2.Response.SerializeToString)}
    generic_handler = grpc.method_handlers_generic_handler('steeleagle.protocol.services.mission_service.Mission', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('steeleagle.protocol.services.mission_service.Mission', rpc_method_handlers)

```
</details>

---
## <><code style={{color: '#b52ee6'}}>class</code></> MissionStub


Used to start a new mission or stop an active mission



<details>
<summary>View Source</summary>
```python
class MissionStub(object):
    """
    Used to start a new mission or stop an active mission
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Upload = channel.unary_unary('/steeleagle.protocol.services.mission_service.Mission/Upload', request_serializer=services_dot_mission__service__pb2.UploadRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.Start = channel.unary_unary('/steeleagle.protocol.services.mission_service.Mission/Start', request_serializer=services_dot_mission__service__pb2.StartRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.Stop = channel.unary_unary('/steeleagle.protocol.services.mission_service.Mission/Stop', request_serializer=services_dot_mission__service__pb2.StopRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.Notify = channel.unary_unary('/steeleagle.protocol.services.mission_service.Mission/Notify', request_serializer=services_dot_mission__service__pb2.NotifyRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)
        self.ConfigureTelemetryStream = channel.unary_unary('/steeleagle.protocol.services.mission_service.Mission/ConfigureTelemetryStream', request_serializer=services_dot_mission__service__pb2.ConfigureTelemetryStreamRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> MissionServicer


Used to start a new mission or stop an active mission


### <><code style={{color: '#10c45b'}}>method</code></> Upload

_Call Type: normal_


Upload a mission for execution
### <><code style={{color: '#10c45b'}}>method</code></> Start

_Call Type: normal_


Start an uploaded mission
### <><code style={{color: '#10c45b'}}>method</code></> Stop

_Call Type: normal_


Stop the current mission
### <><code style={{color: '#10c45b'}}>method</code></> Notify

_Call Type: normal_


Send a notification to the current mission
### <><code style={{color: '#10c45b'}}>method</code></> ConfigureTelemetryStream

_Call Type: normal_


Set the mission telemetry stream parameters

<details>
<summary>View Source</summary>
```python
class MissionServicer(object):
    """
    Used to start a new mission or stop an active mission
    """

    def Upload(self, request, context):
        """Upload a mission for execution
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Start(self, request, context):
        """Start an uploaded mission
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Stop(self, request, context):
        """Stop the current mission
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Notify(self, request, context):
        """Send a notification to the current mission
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def ConfigureTelemetryStream(self, request, context):
        """Set the mission telemetry stream parameters
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> Mission


Used to start a new mission or stop an active mission


### <><code style={{color: '#10c45b'}}>method</code></> Upload

_Call Type: normal_

### <><code style={{color: '#10c45b'}}>method</code></> Start

_Call Type: normal_

### <><code style={{color: '#10c45b'}}>method</code></> Stop

_Call Type: normal_

### <><code style={{color: '#10c45b'}}>method</code></> Notify

_Call Type: normal_

### <><code style={{color: '#10c45b'}}>method</code></> ConfigureTelemetryStream

_Call Type: normal_


<details>
<summary>View Source</summary>
```python
class Mission(object):
    """
    Used to start a new mission or stop an active mission
    """

    @staticmethod
    def Upload(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.mission_service.Mission/Upload', services_dot_mission__service__pb2.UploadRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Start(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.mission_service.Mission/Start', services_dot_mission__service__pb2.StartRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Stop(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.mission_service.Mission/Stop', services_dot_mission__service__pb2.StopRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def Notify(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.mission_service.Mission/Notify', services_dot_mission__service__pb2.NotifyRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)

    @staticmethod
    def ConfigureTelemetryStream(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.mission_service.Mission/ConfigureTelemetryStream', services_dot_mission__service__pb2.ConfigureTelemetryStreamRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)
```
</details>


---
