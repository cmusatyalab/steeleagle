---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# descriptors

---

## <><code style={{color: '#13a6cf'}}>func</code></> get_descriptors

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def get_descriptors():
    descriptor_file = Path(__file__).parent / 'protocol.desc'
    protocol_fds = descriptor_pb2.FileDescriptorSet()
    with open(str(descriptor_file), 'rb') as f:
        protocol_fds.MergeFromString(f.read())
    return protocol_fds

```
</details>

---
