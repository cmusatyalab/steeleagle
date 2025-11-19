---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# edge

---

## <><code class="docs-class">class</code></> EdgePartition

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/tools/map/partitioner/partition#class-partition">Partition</Link></code>*


### <><code class="docs-method">method</code></> generate_partitioned_geopoints

_Call Type: normal_


<details>
<summary>View Source</summary>
```python
class EdgePartition(Partition):
    
    def generate_partitioned_geopoints(self, polygon: Polygon) -> List[GeoPoints]:
        coords = list(polygon.exterior.coords)
        pairs = []
        for i in range(len(coords) - 1):
            p1 = coords[i]
            p2 = coords[i + 1]
            pairs.append(GeoPoints([(p1[0], p1[1]), (p2[0], p2[1])]))
        return pairs

```
</details>


---
