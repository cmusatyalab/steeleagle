---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# compute_service_pb2

Generated protocol buffer code.

---

## <><code style={{color: '#b52ee6'}}>class</code></> GetAvailableDatasinksRequest

*Inherits from: <code>google.protobuf.message.Message</code>*



<details>
<summary>View Source</summary>
```python
DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1eservices/compute_service.proto\x12,steeleagle.protocol.services.compute_service\x1a\x0ccommon.proto\x1a\x1egoogle/protobuf/duration.proto"T\n\x1cGetAvailableDatasinksRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request"q\n\x08Datasink\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\r\n\x05topic\x18\x02 \x01(\t\x12\r\n\x05model\x18\x03 \x01(\t\x12\x0e\n\x06active\x18\x04 \x01(\x08\x12)\n\x06uptime\x18\x05 \x01(\x0b2\x19.google.protobuf.Duration"\xa2\x01\n\x1dGetAvailableDatasinksResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response\x12I\n\tdatasinks\x18\x02 \x03(\x0b26.steeleagle.protocol.services.compute_service.Datasink"q\n\x19ConfigureDatasinksRequest\x124\n\x07request\x18\x01 \x01(\x0b2#.steeleagle.protocol.common.Request\x12\x0c\n\x04name\x18\x02 \x03(\t\x12\x10\n\x08activate\x18\x03 \x03(\x08"T\n\x1aConfigureDatasinksResponse\x126\n\x08response\x18\x01 \x01(\x0b2$.steeleagle.protocol.common.Response2\xea\x02\n\x07Compute\x12\xb2\x01\n\x15GetAvailableDatasinks\x12J.steeleagle.protocol.services.compute_service.GetAvailableDatasinksRequest\x1aK.steeleagle.protocol.services.compute_service.GetAvailableDatasinksResponse"\x00\x12\xa9\x01\n\x12ConfigureDatasinks\x12G.steeleagle.protocol.services.compute_service.ConfigureDatasinksRequest\x1aH.steeleagle.protocol.services.compute_service.ConfigureDatasinksResponse"\x00b\x06proto3')
_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'services.compute_service_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
    DESCRIPTOR._loaded_options = None
    _globals['_GETAVAILABLEDATASINKSREQUEST']._serialized_start = 126

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> Datasink

*Inherits from: <code>google.protobuf.message.Message</code>*



<details>
<summary>View Source</summary>
```python
    _globals['_DATASINK']._serialized_start = 212
    _globals['_DATASINK']._serialized_end = 325
    _globals['_GETAVAILABLEDATASINKSRESPONSE']._serialized_start = 328
    _globals['_GETAVAILABLEDATASINKSRESPONSE']._serialized_end = 490
    _globals['_CONFIGUREDATASINKSREQUEST']._serialized_start = 492
    _globals['_CONFIGUREDATASINKSREQUEST']._serialized_end = 605
    _globals['_CONFIGUREDATASINKSRESPONSE']._serialized_start = 607
    _globals['_CONFIGUREDATASINKSRESPONSE']._serialized_end = 691
    _globals['_COMPUTE']._serialized_start = 694
    _globals['_COMPUTE']._serialized_end = 1056
```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> GetAvailableDatasinksResponse

*Inherits from: <code>google.protobuf.message.Message</code>*





---
## <><code style={{color: '#b52ee6'}}>class</code></> ConfigureDatasinksRequest

*Inherits from: <code>google.protobuf.message.Message</code>*





---
## <><code style={{color: '#b52ee6'}}>class</code></> ConfigureDatasinksResponse

*Inherits from: <code>google.protobuf.message.Message</code>*





---
