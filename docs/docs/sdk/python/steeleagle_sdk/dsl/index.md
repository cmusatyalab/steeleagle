---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# dsl

---

## <><code style={{color: '#de1472'}}>submodule</code></> compiler <Link to="/sdk/python/steeleagle_sdk/dsl/compiler"><GoFileSymlinkFile size={25} /></Link>


---
## <><code style={{color: '#13a6cf'}}>func</code></> build_mission

_Call Type: normal_


Compile DSL source text into a MissionIR object.

### Arguments
**<><code style={{color: '#db2146'}}>arg</code></>&nbsp;&nbsp;dsl_code**&nbsp;&nbsp;(<code>str</code>) <text>&#8212;</text> string representation of a DSL file


### Returns

<code><Link to="/sdk/python/steeleagle_sdk/dsl/compiler/ir#class-missionir">MissionIR</Link></code> <text>&#8212;</text> a mission intermediate representation
<details>
<summary>View Source</summary>
```python
def build_mission(dsl_code: str) -> MissionIR:
    """Compile DSL source text into a MissionIR object.
    
    Args:
        dsl_code (str): string representation of a DSL file

    Returns:
        MissionIR: a mission intermediate representation
    """
    tree = _parser.parse(dsl_code) 
    mission = DroneDSLTransformer().transform(tree)
    logger.info(
        "Compiled DSL: start=%s, actions=%d, events=%d",
        mission.start_action_id, len(mission.actions), len(mission.events),
    )
    return mission

```
</details>

---
