---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';

# compute

---

## <><code style={{color: '#b52ee6'}}>class</code></> DatasinkLocation


Denotes where a datasink is located.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> REMOTE** (<code>0</code>) <text>&#8212;</text> remote location (network hop required)

**<><code style={{color: '#e0a910'}}>attr</code></> LOCAL** (<code>1</code>) <text>&#8212;</text> local location (IPC)



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
## <><code style={{color: '#b52ee6'}}>class</code></> DatasinkInfo


Information about a datasink.    
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> id** (<code>str</code>) <text>&#8212;</text> datasink ID    

**<><code style={{color: '#e0a910'}}>attr</code></> location** (<code><Link to="/sdk/package/steeleagle_sdk/api/datatypes/compute#class-datasinklocation">DatasinkLocation</Link></code>) <text>&#8212;</text> datasink location



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
