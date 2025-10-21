---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# report_service_pb2

Generated protocol buffer code.

---

## <><code style={{color: '#b52ee6'}}>class</code></> ReportMessage

*Inherits from: <code>google.protobuf.message.Message</code>*



<details>
<summary>View Source</summary>
```python
_runtime_version.ValidateProtobufRuntimeVersion(_runtime_version.Domain.PUBLIC, 5, 29, 0, '', 'services/report_service.proto')
_sym_db = _symbol_database.Default()
from .. import common_pb2 as common__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1dservices/report_service.proto\x12+steeleagle.protocol.services.report_service\x1a\x0ccommon.proto"$\n\rReportMessage\x12\x13\n\x0breport_code\x18\x01 \x01(\x05"\x95\x01\n\x11SendReportRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12J\n\x06report\x18\x02 \x01(\x0b2:.steeleagle.protocol.services.report_service.ReportMessage2~\n\x06Report\x12t\n\nSendReport\x12>.steeleagle.protocol.services.report_service.SendReportRequest\x1a$.steeleagle.protocol.common.Response"\x00b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'services.report_service_pb2', _globals)

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> SendReportRequest

*Inherits from: <code>google.protobuf.message.Message</code>*



<details>
<summary>View Source</summary>
```python
    DESCRIPTOR._loaded_options = None
    _globals['_REPORTMESSAGE']._serialized_start = 92
    _globals['_REPORTMESSAGE']._serialized_end = 128
    _globals['_SENDREPORTREQUEST']._serialized_start = 131
    _globals['_SENDREPORTREQUEST']._serialized_end = 280
    _globals['_REPORT']._serialized_start = 282
    _globals['_REPORT']._serialized_end = 408
```
</details>


---
