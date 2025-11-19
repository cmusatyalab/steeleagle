---
toc_max_heading_level: 3
---

import Link from '@docusaurus/Link';

# report_service 
---
## <><code class="docs-class">service</code></> Report


Used to report messages to the Swarm Controller server.

### <><code class="docs-method">rpc</code></> SendReport


Send a report to the server.

#### Accepts
<code><Link to="/sdk/native/services/report_service#message-sendreportrequest">SendReportRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/common#message-response">Response</Link></code>


---

## <><code class="docs-func">message</code></> ReportMessage


Message container for a report.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;report_code**&nbsp;&nbsp;(`int32`) <text>&#8212;</text> integer report code, interpreted by the backend


---
## <><code class="docs-func">message</code></> SendReportRequest


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;request**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#message-request">Request</Link></code>) <text>&#8212;</text> request data

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;report**&nbsp;&nbsp;(<code><Link to="/sdk/native/services/report_service#message-reportmessage">ReportMessage</Link></code>) <text>&#8212;</text> report data


---
