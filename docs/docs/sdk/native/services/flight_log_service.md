---
toc_max_heading_level: 3
---

import Link from '@docusaurus/Link';

# flight_log_service 
---
## <><code class="docs-class">service</code></> FlightLog


Used to log to a flight log.

This service is hosted by a logger instance and is responsible
for writing all system logs to an MCAP file for mission playback.

### <><code class="docs-method">rpc</code></> Log


Basic log endpoint.

Behaves identically to most log endpoints, but writes the data to
an MCAP file instead of the console.

#### Accepts
<code><Link to="/sdk/native/services/flight_log_service#message-logrequest">LogRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>

### <><code class="docs-method">rpc</code></> LogProto


Protobuf log endpoint.

Accepts Protobuf Request/Response types, and writes the data to
an MCAP file. Useful for playback of gRPC calls.

#### Accepts
<code><Link to="/sdk/native/services/flight_log_service#message-logprotorequest">LogProtoRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>


---

## <><code class="docs-func">enum</code></> LogType


Log types (follows Python convention).

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;DEBUG** <text>&#8212;</text> for debugging

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;INFO**&nbsp;&nbsp;(1) <text>&#8212;</text> information

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;PROTO**&nbsp;&nbsp;(2) <text>&#8212;</text> Protobuf objects

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;WARNING**&nbsp;&nbsp;(3) <text>&#8212;</text> warnings

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;ERROR**&nbsp;&nbsp;(4) <text>&#8212;</text> errors

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;CRITICAL**&nbsp;&nbsp;(5) <text>&#8212;</text> critical errors


---
## <><code class="docs-func">message</code></> LogRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;topic**&nbsp;&nbsp;(string) <text>&#8212;</text> topic of the log

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;log**&nbsp;&nbsp;(<code><Link to="/sdk/native/services/flight_log_service#message-logmessage">LogMessage</Link></code>) <text>&#8212;</text> log content


---
## <><code class="docs-func">message</code></> LogMessage


Basic log message.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;type**&nbsp;&nbsp;(<code><Link to="/sdk/native/services/flight_log_service#enum-logtype">LogType</Link></code>) <text>&#8212;</text> type of the log

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;msg**&nbsp;&nbsp;(string) <text>&#8212;</text> message content


---
## <><code class="docs-func">message</code></> ReqRepProto


Protobuf object that is either a Request/Response type.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;response**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-response">Response</Link></code>) <text>&#8212;</text> response data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;name**&nbsp;&nbsp;(string) <text>&#8212;</text> name of the request and associated service

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;content**&nbsp;&nbsp;(string) <text>&#8212;</text> plaintext representation of the proto contents (usually via MessageToDict)


---
## <><code class="docs-func">message</code></> LogProtoRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;topic**&nbsp;&nbsp;(string) <text>&#8212;</text> topic of the log

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;reqrep_proto**&nbsp;&nbsp;(<code><Link to="/sdk/native/services/flight_log_service#message-reqrepproto">ReqRepProto</Link></code>) <text>&#8212;</text> Request/Response object and content


---
