---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# compute

---

## <><code class="docs-class">class</code></> DatasinkLocation

*Inherits from: <code>int</code>, <code>enum.Enum</code>*

Denotes where a datasink is located.
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;REMOTE**&nbsp;&nbsp;(<code>0</code>) <text>&#8212;</text> remote location (network hop required)

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;LOCAL**&nbsp;&nbsp;(<code>1</code>) <text>&#8212;</text> local location (IPC)



<details>
<summary>View Source</summary>
```python
class DatasinkLocation(int, Enum):
    """Denotes where a datasink is located.

    Attributes:
        REMOTE (0): remote location (network hop required)
        LOCAL (1): local location (IPC)
    """
    REMOTE = 0 
    LOCAL = 1 

```
</details>


---
## <><code class="docs-class">class</code></> DatasinkInfo

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-datatype">Datatype</Link></code>*

Information about a datasink.    
#### Attributes
**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;id**&nbsp;&nbsp;(<code>str</code>) <text>&#8212;</text> datasink ID    

**<><code class="docs-attr">attr</code></>&nbsp;&nbsp;location**&nbsp;&nbsp;(<code><Link to="/sdk/python/steeleagle_sdk/api/datatypes/compute#class-datasinklocation">DatasinkLocation</Link></code>) <text>&#8212;</text> datasink location



<details>
<summary>View Source</summary>
```python
@register_data
class DatasinkInfo(Datatype):
    """Information about a datasink.    
    
    Attributes:
        id (str): datasink ID    
        location (DatasinkLocation): datasink location    
    """
    id: str
    location: DatasinkLocation

```
</details>


---
