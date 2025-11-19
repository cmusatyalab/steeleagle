---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# corridor

---

## <><code class="docs-class">class</code></> CorridorPartition

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/tools/map/partitioner/partition#class-partition">Partition</Link></code>*


### <><code class="docs-method">method</code></> generate_partitioned_geopoints

_Call Type: normal_


<details>
<summary>View Source</summary>
```python
@dataclass
class CorridorPartition(Partition):
    spacing: float
    angle_degrees: float

    def generate_partitioned_geopoints(self, polygon: Polygon) -> List[GeoPoints]:
        results: List[GeoPoints] = []
        for line in rotated_infinite_transects(polygon, self.spacing, self.angle_degrees):
            pts = line_polygon_intersection_points(line, polygon)
            if len(pts) >= 2:
                for a, b in zip(pts[0::2], pts[1::2]):
                    p0 = round_xy(a[0], a[1])
                    p1 = round_xy(b[0], b[1])
                    results.append(GeoPoints([p0, p1, p0]))  # mimic [start, end, start]
        return results

```
</details>


---
