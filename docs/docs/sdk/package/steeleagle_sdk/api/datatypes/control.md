---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';

# control

---

## <><code style={{color: '#b52ee6'}}>class</code></> AltitudeMode


Altitude mode switch.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> ABSOLUTE** (<code>0</code>) <text>&#8212;</text> meters above Mean Sea Level

**<><code style={{color: '#e0a910'}}>attr</code></> RELATIVE** (<code>1</code>) <text>&#8212;</text> meters above takeoff position



<details>
<summary>View Source</summary>
```python
class AltitudeMode(int, Enum):
    """Altitude mode switch.

    Attributes:
        ABSOLUTE (0): meters above Mean Sea Level
        RELATIVE (1): meters above takeoff position
    """
    ABSOLUTE = 0 
    RELATIVE = 1 

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> HeadingMode


Heading mode switch.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> TO_TARGET** (<code>0</code>) <text>&#8212;</text> orient towards the target location

**<><code style={{color: '#e0a910'}}>attr</code></> HEADING_START** (<code>1</code>) <text>&#8212;</text> orient towards the given heading



<details>
<summary>View Source</summary>
```python
class HeadingMode(int, Enum):
    """Heading mode switch.

    Attributes:
        TO_TARGET (0): orient towards the target location
        HEADING_START (1): orient towards the given heading
    """
    TO_TARGET = 0 
    HEADING_START = 1 

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> ReferenceFrame


Reference frame mode switch.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> BODY** (<code>0</code>) <text>&#8212;</text> vehicle reference frame

**<><code style={{color: '#e0a910'}}>attr</code></> NEU** (<code>1</code>) <text>&#8212;</text> NEU (North, East, Up) reference frame



<details>
<summary>View Source</summary>
```python
class ReferenceFrame(int, Enum):
    """Reference frame mode switch.

    Attributes:
        BODY (0): vehicle reference frame
        NEU (1): NEU (North, East, Up) reference frame
    """
    BODY = 0 
    NEU = 1 

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> PoseMode


Pose mode switch.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> ANGLE** (<code>0</code>) <text>&#8212;</text> absolute angle

**<><code style={{color: '#e0a910'}}>attr</code></> OFFSET** (<code>1</code>) <text>&#8212;</text> request data // Offset from current

**<><code style={{color: '#e0a910'}}>attr</code></> VELOCITY** (<code>2</code>) <text>&#8212;</text> rotational velocities



<details>
<summary>View Source</summary>
```python
class PoseMode(int, Enum):
    """Pose mode switch.

    Attributes:
        ANGLE (0): absolute angle
        OFFSET (1): request data // Offset from current
        VELOCITY (2): rotational velocities
    """
    ANGLE = 0 
    OFFSET = 1 
    VELOCITY = 2 

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> ImagingSensorConfiguration


Configuration for an imaging sensor.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> id** (<code>int</code>) <text>&#8212;</text> target imaging sensor ID    

**<><code style={{color: '#e0a910'}}>attr</code></> set_primary** (<code>bool</code>) <text>&#8212;</text> set this sensor as the primary stream    

**<><code style={{color: '#e0a910'}}>attr</code></> set_fps** (<code>int</code>) <text>&#8212;</text> target FPS for stream



<details>
<summary>View Source</summary>
```python
@register_data
class ImagingSensorConfiguration(Datatype):
    """Configuration for an imaging sensor.    
    
    Attributes:
        id (int): target imaging sensor ID    
        set_primary (bool): set this sensor as the primary stream    
        set_fps (int): target FPS for stream    
    """
    id: int
    set_primary: bool
    set_fps: int

```
</details>


---
