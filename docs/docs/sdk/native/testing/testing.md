---
toc_max_heading_level: 3
---

import Link from '@docusaurus/Link';

# testing 
---

## <><code class="docs-func">enum</code></> ServiceType


Types of test messages for testing infrastructure

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;CORE_SERVICES**

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;STREAM_SERVICES**&nbsp;&nbsp;(1)

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;MISSION_SERVICE**&nbsp;&nbsp;(2)

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;DRIVER_CONTROL_SERVICE**&nbsp;&nbsp;(3)


---
## <><code class="docs-func">message</code></> ServiceReady


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;readied_service**&nbsp;&nbsp;(<code><Link to="/sdk/native/testing#enum-servicetype">ServiceType</Link></code>) <text>&#8212;</text> Indicates which service is ready for testing


---
