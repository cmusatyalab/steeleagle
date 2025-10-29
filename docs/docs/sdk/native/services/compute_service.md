---
toc_max_heading_level: 3
---

import Link from '@docusaurus/Link';

# compute_service 
---
## <><code class="docs-class">service</code></> Compute


Used to configure datasinks for sensor streams.

This service is used to configure datasink endpoints for frames and 
telemetry post-processing. It maintains an internal consumer list of 
datasinks that the kernel broadcasts frames and telemetry to. RPC 
methods within this service allow for manipulation of this list.

### <><code class="docs-method">rpc</code></> AddDatasinks


Add datasinks to consumer list.

Takes a list of datasinks and adds them to the current consumer list.

#### Accepts
<code><Link to="/sdk/native/services/compute_service#message-adddatasinksrequest">AddDatasinksRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> SetDatasinks


Set the datasink consumer list.

Takes a list of datasinks and replaces the current consumer list with them.

#### Accepts
<code><Link to="/sdk/native/services/compute_service#message-setdatasinksrequest">SetDatasinksRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> RemoveDatasinks


Remove datasinks from consumer list.

Takes a list of datasinks and removes them from the current consumer list.

#### Accepts
<code><Link to="/sdk/native/services/compute_service#message-removedatasinksrequest">RemoveDatasinksRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>


---

## <><code class="docs-func">enum</code></> DatasinkLocation


Denotes where a datasink is located.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;REMOTE** <text>&#8212;</text> remote location (network hop required)

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;LOCAL**&nbsp;&nbsp;(1) <text>&#8212;</text> local location (IPC)


---
## <><code class="docs-func">message</code></> DatasinkInfo


Information about a datasink.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;id**&nbsp;&nbsp;(string) <text>&#8212;</text> datasink ID

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;location**&nbsp;&nbsp;(<code><Link to="/sdk/native/services/compute_service#enum-datasinklocation">DatasinkLocation</Link></code>) <text>&#8212;</text> datasink location


---
## <><code class="docs-func">message</code></> AddDatasinksRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;datasinks**&nbsp;&nbsp;(<code><Link to="/sdk/native/services/compute_service#message-datasinkinfo">DatasinkInfo</Link></code>) <text>&#8212;</text> name of target datasinks


---
## <><code class="docs-func">message</code></> SetDatasinksRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;datasinks**&nbsp;&nbsp;(<code><Link to="/sdk/native/services/compute_service#message-datasinkinfo">DatasinkInfo</Link></code>) <text>&#8212;</text> name of target datasinks


---
## <><code class="docs-func">message</code></> RemoveDatasinksRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;datasinks**&nbsp;&nbsp;(<code><Link to="/sdk/native/services/compute_service#message-datasinkinfo">DatasinkInfo</Link></code>) <text>&#8212;</text> name of target datasinks


---
