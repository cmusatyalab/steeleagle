---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# common

---

## <><code style={{color: '#b52ee6'}}>class</code></> ResponseStatus

*Inherits from: <code>int</code>, <code>enum.Enum</code>*

Response types for RPC functions.

    Values 0-2 (`OK`, `IN_PROGRESS`, `COMPLETED`) are specific to the SteelEagle protocol.
    They determine what phase an RPC call is in:
    - `OK` &#8594; ack
    - `IN_PROGRESS` &#8594; in progress
    - `COMPLETED` &#8594; completed

    These intermediate phases are generally not exposed to user-facing code and are only used 
    for streaming methods. In contrast to normal gRPC procedure, a call is only considered complete
    on a response of `COMPLETED` instead of `OK`. If an error occurs, SteelEagle defers to gRPC error 
    codes, 3-18. More details on these codes can be found [here](https://grpc.github.io/grpc/core/md_doc_statuscodes.html).
    Note that the value of these codes is offset by 2 from their original form (e.g. `CANCELLED` = 3 vs = 1).
    Therefore, for error codes, the transformation from gRPC to SteelEagle response code is to add
    2 to the code. The only codes that differ from their gRPC meaning are codes 9 and 18.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;OK**&nbsp;&nbsp;(<code>0</code>) <text>&#8212;</text> command acknowledged

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;IN_PROGRESS**&nbsp;&nbsp;(<code>1</code>) <text>&#8212;</text> command in progress

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;COMPLETED**&nbsp;&nbsp;(<code>2</code>) <text>&#8212;</text> command finished without error

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;CANCELLED**&nbsp;&nbsp;(<code>3</code>) <text>&#8212;</text> the operation was cancelled, typically by the caller

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;UNKNOWN**&nbsp;&nbsp;(<code>4</code>) <text>&#8212;</text> unknown error

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;INVALID_ARGUMENT**&nbsp;&nbsp;(<code>5</code>) <text>&#8212;</text> the client specified an invalid argument

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;DEADLINE_EXCEEDED**&nbsp;&nbsp;(<code>6</code>) <text>&#8212;</text> the deadline expired before the operation could complete

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;NOT_FOUND**&nbsp;&nbsp;(<code>7</code>) <text>&#8212;</text> some requested entity was not found

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;ALREADY_EXISTS**&nbsp;&nbsp;(<code>8</code>) <text>&#8212;</text> an entity the client attempted to create already exists

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;PERMISSION_DENIED**&nbsp;&nbsp;(<code>9</code>) <text>&#8212;</text> the provided identity is not permitted to execute this operation by the current law (unique to SteelEagle)

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;RESOURCE_EXHAUSTED**&nbsp;&nbsp;(<code>10</code>) <text>&#8212;</text> some resource has been exhausted

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;FAILED_PRECONDITION**&nbsp;&nbsp;(<code>11</code>) <text>&#8212;</text> the operation was rejected because the system is not in a state required for the operation's execution

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;ABORTED**&nbsp;&nbsp;(<code>12</code>) <text>&#8212;</text> the operation was aborted, typically due to a concurrency issue such as a sequencer check failure or transaction abort

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;OUT_OF_RANGE**&nbsp;&nbsp;(<code>13</code>) <text>&#8212;</text> the operation was attempted past the valid range

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;UNIMPLEMENTED**&nbsp;&nbsp;(<code>14</code>) <text>&#8212;</text> the operation is not implemented/supported by the service

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;INTERNAL**&nbsp;&nbsp;(<code>15</code>) <text>&#8212;</text> an internal error occured while executing the operation

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;UNAVAILABLE**&nbsp;&nbsp;(<code>16</code>) <text>&#8212;</text> the service is currently unavailable

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;DATA_LOSS**&nbsp;&nbsp;(<code>17</code>) <text>&#8212;</text> unrecoverable data loss or corruption

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;UNAUTHENTICATED**&nbsp;&nbsp;(<code>18</code>) <text>&#8212;</text> the client failed to provide an identity (unique to SteelEagle)



<details>
<summary>View Source</summary>
```python
class ResponseStatus(int, Enum):
    """Response types for RPC functions.

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

    Attributes:
        OK (0): command acknowledged
        IN_PROGRESS (1): command in progress
        COMPLETED (2): command finished without error
        CANCELLED (3): the operation was cancelled, typically by the caller
        UNKNOWN (4): unknown error
        INVALID_ARGUMENT (5): the client specified an invalid argument
        DEADLINE_EXCEEDED (6): the deadline expired before the operation could complete
        NOT_FOUND (7): some requested entity was not found
        ALREADY_EXISTS (8): an entity the client attempted to create already exists
        PERMISSION_DENIED (9): the provided identity is not permitted to execute this operation by the current law (unique to SteelEagle)
        RESOURCE_EXHAUSTED (10): some resource has been exhausted
        FAILED_PRECONDITION (11): the operation was rejected because the system is not in a state required for the operation's execution
        ABORTED (12): the operation was aborted, typically due to a concurrency issue such as a sequencer check failure or transaction abort
        OUT_OF_RANGE (13): the operation was attempted past the valid range
        UNIMPLEMENTED (14): the operation is not implemented/supported by the service
        INTERNAL (15): an internal error occured while executing the operation
        UNAVAILABLE (16): the service is currently unavailable
        DATA_LOSS (17): unrecoverable data loss or corruption
        UNAUTHENTICATED (18): the client failed to provide an identity (unique to SteelEagle)
    """
    OK = 0 
    IN_PROGRESS = 1 
    COMPLETED = 2 
    CANCELLED = 3 
    UNKNOWN = 4 
    INVALID_ARGUMENT = 5 
    DEADLINE_EXCEEDED = 6 
    NOT_FOUND = 7 
    ALREADY_EXISTS = 8 
    PERMISSION_DENIED = 9 
    RESOURCE_EXHAUSTED = 10 
    FAILED_PRECONDITION = 11 
    ABORTED = 12 
    OUT_OF_RANGE = 13 
    UNIMPLEMENTED = 14 
    INTERNAL = 15 
    UNAVAILABLE = 16 
    DATA_LOSS = 17 
    UNAUTHENTICATED = 18 

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> Response

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Global response message returned by all core services.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;status**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/common#class-responsestatus">ResponseStatus</Link></code>) <text>&#8212;</text> response status    

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;response_string**&nbsp;&nbsp;(<code>Optional[str]</code>) <text>&#8212;</text> detailed message on reason for response    

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;timestamp**&nbsp;&nbsp;(<code>google.protobuf.timestamp_pb2.Timestamp</code>) <text>&#8212;</text> response timestamp



<details>
<summary>View Source</summary>
```python
@register_data
class Response(Datatype):
    """Global response message returned by all core services.    
    
    Attributes:
        status (ResponseStatus): response status    
        response_string (Optional[str]): detailed message on reason for response    
        timestamp (Timestamp): response timestamp    
    """
    status: ResponseStatus
    response_string: Optional[str]
    timestamp: Timestamp

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> Pose

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Angular offsets or poses in 3 dimensions.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;pitch**&nbsp;&nbsp;(<code>Optional[float]</code>) <text>&#8212;</text> pitch [degrees]    

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;roll**&nbsp;&nbsp;(<code>Optional[float]</code>) <text>&#8212;</text> roll [degrees]    

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;yaw**&nbsp;&nbsp;(<code>Optional[float]</code>) <text>&#8212;</text> yaw [degrees]



<details>
<summary>View Source</summary>
```python
@register_data
class Pose(Datatype):
    """Angular offsets or poses in 3 dimensions.    
    
    Attributes:
        pitch (Optional[float]): pitch [degrees]    
        roll (Optional[float]): roll [degrees]    
        yaw (Optional[float]): yaw [degrees]    
    """
    pitch: Optional[float]
    roll: Optional[float]
    yaw: Optional[float]

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> Velocity

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Representation of velocity in 3-dimensions.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;x_vel**&nbsp;&nbsp;(<code>Optional[float]</code>) <text>&#8212;</text> forward/north velocity [meters/s]    

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;y_vel**&nbsp;&nbsp;(<code>Optional[float]</code>) <text>&#8212;</text> right/east velocity [meters/s]    

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;z_vel**&nbsp;&nbsp;(<code>Optional[float]</code>) <text>&#8212;</text> up velocity [meters/s]    

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;angular_vel**&nbsp;&nbsp;(<code>Optional[float]</code>) <text>&#8212;</text> angular velocity [degrees/s]



<details>
<summary>View Source</summary>
```python
@register_data
class Velocity(Datatype):
    """Representation of velocity in 3-dimensions.    
    
    Attributes:
        x_vel (Optional[float]): forward/north velocity [meters/s]    
        y_vel (Optional[float]): right/east velocity [meters/s]    
        z_vel (Optional[float]): up velocity [meters/s]    
        angular_vel (Optional[float]): angular velocity [degrees/s]    
    """
    x_vel: Optional[float]
    y_vel: Optional[float]
    z_vel: Optional[float]
    angular_vel: Optional[float]

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> Position

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Position offset relative to home or current location.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;x**&nbsp;&nbsp;(<code>Optional[float]</code>) <text>&#8212;</text> forward/north offset [meters]    

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;y**&nbsp;&nbsp;(<code>Optional[float]</code>) <text>&#8212;</text> right/east offset [meters]    

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;z**&nbsp;&nbsp;(<code>Optional[float]</code>) <text>&#8212;</text> up offset [meters]    

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;angle**&nbsp;&nbsp;(<code>Optional[float]</code>) <text>&#8212;</text> angular offset [degrees]



<details>
<summary>View Source</summary>
```python
@register_data
class Position(Datatype):
    """Position offset relative to home or current location.    
    
    Attributes:
        x (Optional[float]): forward/north offset [meters]    
        y (Optional[float]): right/east offset [meters]    
        z (Optional[float]): up offset [meters]    
        angle (Optional[float]): angular offset [degrees]    
    """
    x: Optional[float]
    y: Optional[float]
    z: Optional[float]
    angle: Optional[float]

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> Location

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Location in global coordinates.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;latitude**&nbsp;&nbsp;(<code>Optional[float]</code>) <text>&#8212;</text> global latitude [degrees]    

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;longitude**&nbsp;&nbsp;(<code>Optional[float]</code>) <text>&#8212;</text> global longitude [degrees]    

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;altitude**&nbsp;&nbsp;(<code>Optional[float]</code>) <text>&#8212;</text> altitude above MSL or takeoff [meters]    

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;heading**&nbsp;&nbsp;(<code>Optional[float]</code>) <text>&#8212;</text> global heading [degrees]



<details>
<summary>View Source</summary>
```python
@register_data
class Location(Datatype):
    """Location in global coordinates.    
    
    Attributes:
        latitude (Optional[float]): global latitude [degrees]    
        longitude (Optional[float]): global longitude [degrees]    
        altitude (Optional[float]): altitude above MSL or takeoff [meters]    
        heading (Optional[float]): global heading [degrees]    
    """
    latitude: Optional[float]
    longitude: Optional[float]
    altitude: Optional[float]
    heading: Optional[float]

```
</details>


---
