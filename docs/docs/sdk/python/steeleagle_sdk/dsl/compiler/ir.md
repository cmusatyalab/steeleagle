---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# ir

---

## <><code class="docs-class">class</code></> ActionIR




<details>
<summary>View Source</summary>
```python
@dataclass
class ActionIR:
    type_name: str
    action_id: str
    attributes: Dict[str, Any] = field(default_factory=dict)

```
</details>


---
## <><code class="docs-class">class</code></> EventIR




<details>
<summary>View Source</summary>
```python
@dataclass
class EventIR:
    type_name: str
    event_id: str
    attributes: Dict[str, Any] = field(default_factory=dict)

```
</details>


---
## <><code class="docs-class">class</code></> DatumIR




<details>
<summary>View Source</summary>
```python
@dataclass
class DatumIR:
    type_name: str
    datum_id: str
    attributes: Dict[str, Any] = field(default_factory=dict)

```
</details>


---
## <><code class="docs-class">class</code></> MissionIR




<details>
<summary>View Source</summary>
```python
@dataclass
class MissionIR:
    actions: Dict[str, ActionIR]
    events: Dict[str, EventIR]
    data: Dict[str, DatumIR]
    start_action_id: str
    # transitions: (action, event) -> next_action
    transitions: Dict[str, Dict[str, str]]

```
</details>


---
