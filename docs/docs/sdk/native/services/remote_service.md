---
toc_max_heading_level: 3
---

import Link from '@docusaurus/Link';

# remote_service 
---
## <><code class="docs-class">service</code></> Remote


Used to control a vehicle remotely over ZeroMQ, usually hosted
on the server

### <><code class="docs-method">rpc</code></> Command


Sends a service request to a vehicle core service (Control, Mission, etc.)
over ZeroMQ and returns the response

#### Accepts
<code><Link to="/sdk/native/services/remote_service#message-commandrequest">CommandRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> CompileMission


#### Accepts
<code><Link to="/sdk/native/services/remote_service#message-compilemissionrequest">CompileMissionRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/services/remote_service#message-compilemissionresponse">CompileMissionResponse</Link></code>


---

## <><code class="docs-func">message</code></> CompileMissionRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;dsl_content**&nbsp;&nbsp;(string)


---
## <><code class="docs-func">message</code></> CompileMissionResponse


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;compiled_dsl_content**&nbsp;&nbsp;(string)

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;response**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-response">Response</Link></code>)


---
## <><code class="docs-func">message</code></> CommandRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;sequence_number**&nbsp;&nbsp;(uint32) <text>&#8212;</text> Since command sequencing is not built-in to ZeroMQ, it must be done manually; this will be set automatically by the server

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code>/google/protobuf/Any</code>) <text>&#8212;</text> Contains request data for an RPC call

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;method_name**&nbsp;&nbsp;(string) <text>&#8212;</text> Fully qualified method name

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;identity**&nbsp;&nbsp;(string) <text>&#8212;</text> Identity of the sender

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;vehicle_id**&nbsp;&nbsp;(string) <text>&#8212;</text> Target vehicle to send to


---
## <><code class="docs-func">message</code></> CommandResponse


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;sequence_number**&nbsp;&nbsp;(uint32) <text>&#8212;</text> This response is not seen by the client, but is a wrapper around a normal response; this is done for sequence_number correlation

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;response**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-response">Response</Link></code>) <text>&#8212;</text> Generic response


---
