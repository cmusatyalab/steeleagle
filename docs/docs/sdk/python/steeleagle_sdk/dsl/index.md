---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# dsl

---

## <><code class="docs-submodule">submodule</code></> compiler <Link to="/sdk/python/steeleagle_sdk/dsl/compiler"><GoFileSymlinkFile size={25} /></Link>


---
## <><code class="docs-func">func</code></> build_mission

_Call Type: normal_


Compile DSL source text into a MissionIR object.

### Arguments
**<><code class="docs-arg">arg</code></>&nbsp;&nbsp;dsl_code**&nbsp;&nbsp;(<code>str</code>) <text>&#8212;</text> string representation of a DSL file


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
## <><code class="docs-func">func</code></> cli_compile_dsl

_Call Type: normal_


Command line utility for compiling DSL scripts.

Command line script that takes a DSL file as input and writes the compiled mission file
to the specified output path.

### Arguments
**<><code class="docs-arg">arg</code></>&nbsp;&nbsp;dsl_file**&nbsp;&nbsp;(<code>str</code>) <text>&#8212;</text> input DSL file path (positional argument 0, required)

**<><code class="docs-arg">arg</code></>&nbsp;&nbsp;output**&nbsp;&nbsp;(<code>str</code>) <text>&#8212;</text> output mission JSON path (`--output` or `-o`, default: `./mission.json`)

<details>
<summary>View Source</summary>
```python
def cli_compile_dsl():
    """Command line utility for compiling DSL scripts.

    Command line script that takes a DSL file as input and writes the compiled mission file
    to the specified output path.

    Args:
        dsl_file (str): input DSL file path (positional argument 0, required)
        output (str): output mission JSON path (`--output` or `-o`, default: `./mission.json`)
    """
    import argparse
    from dataclasses import asdict
    import json
    parser = argparse.ArgumentParser(description="SteelEagle DSL compiler.")
    parser.add_argument("dsl_file", help="Path to DSL file")
    parser.add_argument("-o", "--output", type=str, default="mission.json", help="Name of the output file (type: JSON)")
    args = parser.parse_args()

    mission_json_text = ''
    with open(args.dsl_file, 'r') as file:
        dsl_content = file.read()
        mission = build_mission(dsl_content)
        mission_json_text = json.dumps(asdict(mission))
        print("Mission compiled!")

    with open(args.output, 'w') as file:
        file.write(mission_json_text)
        print(f"Wrote contents to {args.output}.")

```
</details>

---
