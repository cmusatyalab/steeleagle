---
toc_max_heading_level: 3
---

import Link from '@docusaurus/Link';

# common 
---

## <><code class="docs-func">enum</code></> ResponseStatus


Response types for RPC functions.

Values 0-2 (`OK`, `IN_PROGRESS`, `COMPLETED`) are specific to the SteelEagle protocol.
They determine what phase an RPC call is in:
- `OK` -> ack
- `IN_PROGRESS` -> in progress
- `COMPLETED` -> completed

These intermediate phases are generally not exposed to user-facing code and are only used 
for streaming methods. In contrast to normal gRPC procedure, a call is only considered complete
on a response of `COMPLETED` instead of `OK`. If an error occurs, SteelEagle defers to gRPC error 
codes, 3-18. More details on these codes can be found [here](https://grpc.github.io/grpc/core/md_doc_statuscodes.html).
Note that the value of these codes is offset by 2 from their original form (e.g. `CANCELLED` = 3 vs = 1).
Therefore, for error codes, the transformation from gRPC to SteelEagle response code is to add
2 to the code. The only codes that differ from their gRPC meaning are codes 9 and 18.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;OK** <text>&#8212;</text> command acknowledged

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;IN_PROGRESS**&nbsp;&nbsp;(1) <text>&#8212;</text> command in progress

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;COMPLETED**&nbsp;&nbsp;(2) <text>&#8212;</text> command finished without error

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;CANCELLED**&nbsp;&nbsp;(3) <text>&#8212;</text> the operation was cancelled, typically by the caller

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;UNKNOWN**&nbsp;&nbsp;(4) <text>&#8212;</text> unknown error

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;INVALID_ARGUMENT**&nbsp;&nbsp;(5) <text>&#8212;</text> the client specified an invalid argument

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;DEADLINE_EXCEEDED**&nbsp;&nbsp;(6) <text>&#8212;</text> the deadline expired before the operation could complete

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;NOT_FOUND**&nbsp;&nbsp;(7) <text>&#8212;</text> some requested entity was not found

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;ALREADY_EXISTS**&nbsp;&nbsp;(8) <text>&#8212;</text> an entity the client attempted to create already exists

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;PERMISSION_DENIED**&nbsp;&nbsp;(9) <text>&#8212;</text> the provided identity is not permitted to execute this operation by the current law (unique to SteelEagle)

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;RESOURCE_EXHAUSTED**&nbsp;&nbsp;(10) <text>&#8212;</text> some resource has been exhausted

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;FAILED_PRECONDITION**&nbsp;&nbsp;(11) <text>&#8212;</text> the operation was rejected because the system is not in a state required for the operation's execution

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;ABORTED**&nbsp;&nbsp;(12) <text>&#8212;</text> the operation was aborted, typically due to a concurrency issue such as a sequencer check failure or transaction abort

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;OUT_OF_RANGE**&nbsp;&nbsp;(13) <text>&#8212;</text> the operation was attempted past the valid range

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;UNIMPLEMENTED**&nbsp;&nbsp;(14) <text>&#8212;</text> the operation is not implemented/supported by the service

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;INTERNAL**&nbsp;&nbsp;(15) <text>&#8212;</text> an internal error occured while executing the operation

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;UNAVAILABLE**&nbsp;&nbsp;(16) <text>&#8212;</text> the service is currently unavailable

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;DATA_LOSS**&nbsp;&nbsp;(17) <text>&#8212;</text> unrecoverable data loss or corruption

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;UNAUTHENTICATED**&nbsp;&nbsp;(18) <text>&#8212;</text> the client failed to provide an identity (unique to SteelEagle)


---
## <><code class="docs-func">message</code></> Request


Request object for additional request info.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;timestamp**&nbsp;&nbsp;(<code>/google/protobuf/Timestamp</code>) <text>&#8212;</text> request timestamp


---
## <><code class="docs-func">message</code></> Response


Global response message returned by all core services.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;status**&nbsp;&nbsp;(<code><Link to="/sdk/native/common#enum-responsestatus">ResponseStatus</Link></code>) <text>&#8212;</text> response status

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;response_string**&nbsp;&nbsp;(string) <text>&#8212;</text> detailed message on reason for response

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;timestamp**&nbsp;&nbsp;(<code>/google/protobuf/Timestamp</code>) <text>&#8212;</text> response timestamp


---
## <><code class="docs-func">message</code></> Pose


Angular offsets or poses in 3 dimensions.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;pitch**&nbsp;&nbsp;(double) <text>&#8212;</text> pitch [degrees]

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;roll**&nbsp;&nbsp;(double) <text>&#8212;</text> roll [degrees]

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;yaw**&nbsp;&nbsp;(double) <text>&#8212;</text> yaw [degrees]


---
## <><code class="docs-func">message</code></> Velocity


Representation of velocity in 3-dimensions.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;x_vel**&nbsp;&nbsp;(double) <text>&#8212;</text> forward/north velocity [meters/s]

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;y_vel**&nbsp;&nbsp;(double) <text>&#8212;</text> right/east velocity [meters/s]

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;z_vel**&nbsp;&nbsp;(double) <text>&#8212;</text> up velocity [meters/s]

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;angular_vel**&nbsp;&nbsp;(double) <text>&#8212;</text> angular velocity [degrees/s]


---
## <><code class="docs-func">message</code></> Position


Position offset relative to home or current location.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;x**&nbsp;&nbsp;(double) <text>&#8212;</text> forward/north offset [meters]

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;y**&nbsp;&nbsp;(double) <text>&#8212;</text> right/east offset [meters]

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;z**&nbsp;&nbsp;(double) <text>&#8212;</text> up offset [meters]

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;angle**&nbsp;&nbsp;(double) <text>&#8212;</text> angular offset [degrees]


---
## <><code class="docs-func">message</code></> Location


Location in global coordinates.

#### Fields
**<><code class="docs-attr">field</code></>&nbsp;&nbsp;latitude**&nbsp;&nbsp;(double) <text>&#8212;</text> global latitude [degrees]

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;longitude**&nbsp;&nbsp;(double) <text>&#8212;</text> global longitude [degrees]

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;altitude**&nbsp;&nbsp;(double) <text>&#8212;</text> altitude above MSL or takeoff [meters]

**<><code class="docs-attr">field</code></>&nbsp;&nbsp;heading**&nbsp;&nbsp;(double) <text>&#8212;</text> global heading [degrees]


---
