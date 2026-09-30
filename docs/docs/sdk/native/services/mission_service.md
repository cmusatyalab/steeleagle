---
toc_max_heading_level: 3
---

import Link from '@docusaurus/Link';

# mission_service
---
## <><code class="docs-class">service</code></> MissionService


Used to upload, start, and stop a vehicle's mission. This service is hosted by the vehicle's mission plugin; the swarm controller proxies it to multiple vehicles via `SwarmService`, which returns a per-vehicle response stream.

### <><code class="docs-method">rpc</code></> StartMission


Order a vehicle to start its uploaded mission. This enables autonomous control mode, which can be interrupted by sending a `StopMission` or `SwarmHold`. Fails with `FAILED_PRECONDITION` if no mission has been uploaded or one is already running.

#### Accepts
<code><Link to="/sdk/native/services/mission_service#message-startmissionrequest">StartMissionRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/services/mission_service#message-startmissionresponse">StartMissionResponse</Link></code>

### <><code class="docs-method">rpc</code></> UploadMission


Stream a compiled mission binary to a vehicle (client-streaming). The first message must carry a `header`; every later message carries a `chunk` (256 KiB is the chunk size used by the swarm controller). The upload is committed only if the byte count and SHA-256 match the header and the binary is an ELF executable for the vehicle's architecture; a failed or cancelled upload never replaces a previously uploaded mission. Start it with a subsequent `StartMission`.

Errors: `INVALID_ARGUMENT` (malformed header, wrong architecture, not an ELF executable, size or hash mismatch, larger than 128 MiB), `FAILED_PRECONDITION` (a mission is running), `ABORTED` (another upload is already in progress).

#### Accepts
stream <code><Link to="/sdk/native/services/mission_service#message-uploadmissionrequest">UploadMissionRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/services/mission_service#message-uploadmissionresponse">UploadMissionResponse</Link></code>

### <><code class="docs-method">rpc</code></> StopMission


Order a vehicle to stop its running mission. This enables manual control mode. A no-op if no mission is running.

#### Accepts
<code><Link to="/sdk/native/services/mission_service#message-stopmissionrequest">StopMissionRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/services/mission_service#message-stopmissionresponse">StopMissionResponse</Link></code>

### <><code class="docs-method">rpc</code></> GetMissionInfo


Report what this mission service can run, so an uploader can pick the matching binary variant before sending any bytes.

#### Accepts
<code><Link to="/sdk/native/services/mission_service#message-getmissioninforequest">GetMissionInfoRequest</Link></code>

#### Returns
<code><Link to="/sdk/native/services/mission_service#message-getmissioninforesponse">GetMissionInfoResponse</Link></code>


---

## <><code class="docs-func">message</code></> MissionHeader


Describes the mission binary that follows in an upload stream.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;arch**&nbsp;&nbsp;(`string`) <text>&#8212;</text> GOARCH-style architecture the binary was built for: `amd64` or `arm64`

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;size**&nbsp;&nbsp;(`uint64`) <text>&#8212;</text> Exact byte length of the binary

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;sha256**&nbsp;&nbsp;(`bytes`) <text>&#8212;</text> 32-byte SHA-256 digest of the binary


---
## <><code class="docs-func">message</code></> UploadMissionRequest


One message of an upload stream. Exactly one of the fields is set (oneof `part`).

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;header**&nbsp;&nbsp;(<code><Link to="/sdk/native/services/mission_service#message-missionheader">MissionHeader</Link></code>) <text>&#8212;</text> First message only

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;chunk**&nbsp;&nbsp;(`bytes`) <text>&#8212;</text> Every later message: the next slice of the binary


---
## <><code class="docs-func">message</code></> UploadMissionResponse


Empty; success is indicated by an OK status.


---
## <><code class="docs-func">message</code></> GetMissionInfoRequest


Empty.


---
## <><code class="docs-func">message</code></> GetMissionInfoResponse


#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;arch**&nbsp;&nbsp;(`string`) <text>&#8212;</text> GOARCH of the host the mission service runs on


---
## <><code class="docs-func">message</code></> StartMissionRequest


Empty.


---
## <><code class="docs-func">message</code></> StartMissionResponse


Empty; success is indicated by an OK status.


---
## <><code class="docs-func">message</code></> StopMissionRequest


Empty.


---
## <><code class="docs-func">message</code></> StopMissionResponse


Empty; success is indicated by an OK status.


---
