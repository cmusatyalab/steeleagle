---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# control

---

## <><code class="docs-class">class</code></> AltitudeMode

*Inherits from: <code>int</code>, <code>enum.Enum</code>*

Altitude mode switch.
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;ABSOLUTE**&nbsp;&nbsp;(<code>0</code>) <text>&#8212;</text> meters above Mean Sea Level

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;RELATIVE**&nbsp;&nbsp;(<code>1</code>) <text>&#8212;</text> meters above takeoff position



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
## <><code class="docs-class">class</code></> HeadingMode

*Inherits from: <code>int</code>, <code>enum.Enum</code>*

Heading mode switch.
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;TO_TARGET**&nbsp;&nbsp;(<code>0</code>) <text>&#8212;</text> orient towards the target location

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;HEADING_START**&nbsp;&nbsp;(<code>1</code>) <text>&#8212;</text> orient towards the given heading



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
## <><code class="docs-class">class</code></> ReferenceFrame

*Inherits from: <code>int</code>, <code>enum.Enum</code>*

Reference frame mode switch.
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;BODY**&nbsp;&nbsp;(<code>0</code>) <text>&#8212;</text> vehicle reference frame

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;NEU**&nbsp;&nbsp;(<code>1</code>) <text>&#8212;</text> NEU (North, East, Up) reference frame



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
## <><code class="docs-class">class</code></> PoseMode

*Inherits from: <code>int</code>, <code>enum.Enum</code>*

Pose mode switch.
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;ANGLE**&nbsp;&nbsp;(<code>0</code>) <text>&#8212;</text> absolute angle

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;OFFSET**&nbsp;&nbsp;(<code>1</code>) <text>&#8212;</text> request data // Offset from current

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;VELOCITY**&nbsp;&nbsp;(<code>2</code>) <text>&#8212;</text> rotational velocities



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
## <><code class="docs-class">class</code></> ImagingSensorConfiguration

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Configuration for an imaging sensor.    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;id**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> target imaging sensor ID    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;set_primary**&nbsp;&nbsp;(<code>bool</code>) <text>&#8212;</text> set this sensor as the primary stream    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;set_fps**&nbsp;&nbsp;(<code>int</code>) <text>&#8212;</text> target FPS for stream



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
