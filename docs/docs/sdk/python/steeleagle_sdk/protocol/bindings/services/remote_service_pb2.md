---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# remote_service_pb2

Generated protocol buffer code.

---

## <><code style={{color: '#b52ee6'}}>class</code></> RemoteControlRequest

*Inherits from: <code>google.protobuf.message.Message</code>*



<details>
<summary>View Source</summary>
```python
_sym_db = _symbol_database.Default()
from google.protobuf import any_pb2 as google_dot_protobuf_dot_any__pb2
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1dservices/remote_service.proto\x12+steeleagle.protocol.services.remote_service\x1a\x19google/protobuf/any.proto"\x85\x01\n\x14RemoteControlRequest\x12\x17\n\x0fsequence_number\x18\x01 \x01(\r\x12-\n\x0fcontrol_request\x18\x02 \x01(\x0b2\x14.google.protobuf.Any\x12\x13\n\x0bmethod_name\x18\x03 \x01(\t\x12\x10\n\x08identity\x18\x04 \x01(\t"r\n\x15RemoteControlResponse\x12\x17\n\x0fsequence_number\x18\x01 \x01(\r\x12.\n\x10control_response\x18\x02 \x01(\x0b2\x14.google.protobuf.Any\x12\x10\n\x08identity\x18\x03 \x01(\t2\xa3\x01\n\x06Remote\x12\x98\x01\n\rRemoteControl\x12A.steeleagle.protocol.services.remote_service.RemoteControlRequest\x1aB.steeleagle.protocol.services.remote_service.RemoteControlResponse"\x00b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'services.remote_service_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_REMOTECONTROLREQUEST']._serialized_start = 106
    _globals['_REMOTECONTROLREQUEST']._serialized_end = 239
    _globals['_REMOTECONTROLRESPONSE']._serialized_start = 241
    _globals['_REMOTECONTROLRESPONSE']._serialized_end = 355
    _globals['_REMOTE']._serialized_start = 358

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> RemoteControlResponse

*Inherits from: <code>google.protobuf.message.Message</code>*





---
