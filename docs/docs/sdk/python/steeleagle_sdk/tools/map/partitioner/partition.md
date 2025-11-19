---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# partition

---

## <><code class="docs-class">class</code></> Partition


Abstract base: generate partitioned GeoPoints (planar coordinates).


### <><code class="docs-method">method</code></> generate_partitioned_geopoints

_Call Type: normal_


<details>
<summary>View Source</summary>
```python
class Partition:
    """Abstract base: generate partitioned GeoPoints (planar coordinates)."""
    def generate_partitioned_geopoints(self, polygon: Polygon) -> List[GeoPoints]:
        raise NotImplementedError

```
</details>


---
