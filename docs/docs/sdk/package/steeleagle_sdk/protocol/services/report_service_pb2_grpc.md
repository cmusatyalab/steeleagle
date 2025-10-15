---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';

# report_service_pb2_grpc

Client and server classes corresponding to protobuf-defined services.

---

## <><code style={{color: '#13a6cf'}}>func</code></> add_ReportServicer_to_server

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def add_ReportServicer_to_server(servicer, server):
    rpc_method_handlers = {'SendReport': grpc.unary_unary_rpc_method_handler(servicer.SendReport, request_deserializer=services_dot_report__service__pb2.SendReportRequest.FromString, response_serializer=common__pb2.Response.SerializeToString)}
    generic_handler = grpc.method_handlers_generic_handler('steeleagle.protocol.services.report_service.Report', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('steeleagle.protocol.services.report_service.Report', rpc_method_handlers)

```
</details>

---
## <><code style={{color: '#b52ee6'}}>class</code></> ReportStub


Used to report messages to the Swarm Controller server.



<details>
<summary>View Source</summary>
```python
class ReportStub(object):
    """
    Used to report messages to the Swarm Controller server.
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.SendReport = channel.unary_unary('/steeleagle.protocol.services.report_service.Report/SendReport', request_serializer=services_dot_report__service__pb2.SendReportRequest.SerializeToString, response_deserializer=common__pb2.Response.FromString, _registered_method=True)

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> ReportServicer


Used to report messages to the Swarm Controller server.


### <><code style={{color: '#10c45b'}}>method</code></> SendReport

_Call Type: normal_


Send a report to the server.

<details>
<summary>View Source</summary>
```python
class ReportServicer(object):
    """
    Used to report messages to the Swarm Controller server.
    """

    def SendReport(self, request, context):
        """Send a report to the server.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> Report


Used to report messages to the Swarm Controller server.


### <><code style={{color: '#10c45b'}}>method</code></> SendReport

_Call Type: normal_


<details>
<summary>View Source</summary>
```python
class Report(object):
    """
    Used to report messages to the Swarm Controller server.
    """

    @staticmethod
    def SendReport(request, target, options=(), channel_credentials=None, call_credentials=None, insecure=False, compression=None, wait_for_ready=None, timeout=None, metadata=None):
        return grpc.experimental.unary_unary(request, target, '/steeleagle.protocol.services.report_service.Report/SendReport', services_dot_report__service__pb2.SendReportRequest.SerializeToString, common__pb2.Response.FromString, options, channel_credentials, insecure, call_credentials, compression, wait_for_ready, timeout, metadata, _registered_method=True)
```
</details>


---
