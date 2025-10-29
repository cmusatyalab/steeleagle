---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# resolver

---

## <><code class="docs-func">func</code></> resolve_symbols

_Call Type: normal_


Replace string IDs in attributes with *instances* of the referenced data models
when the target field is a model type. Also instantiate inline data constructors
in action/event attributes. For Data objects, resolve nested references inside
their attribute dicts so that later instantiation sees already-resolved values.
<details>
<summary>View Source</summary>
```python
def resolve_symbols(mir: MissionIR) -> MissionIR:
    """
    Replace string IDs in attributes with *instances* of the referenced data models
    when the target field is a model type. Also instantiate inline data constructors
    in action/event attributes. For Data objects, resolve nested references inside
    their attribute dicts so that later instantiation sees already-resolved values.
    """
    logger.info(
        "resolve_symbols: start (actions=%d, events=%d, data=%d)",
        len(mir.actions), len(mir.events), len(mir.data)
    )

    # 1) DATA — resolve references inside DatumIR.attributes (but keep as dict)
    for did, dir_ in mir.data.items():
        data_cls = get_data(dir_.type_name)
        if not data_cls:
            logger.warning("resolve_symbols: data '%s' type '%s' not registered", did, dir_.type_name)
            raise ResolverException(f"Data '{did}' type '{dir_.type_name}' not registered")
        resolved_attrs = dict(dir_.attributes)
        for fname, ftype in _iter_model_fields(data_cls):
            if fname in resolved_attrs:
                resolved_attrs[fname] = _resolve_value_for_field(resolved_attrs[fname], ftype, mir.data)
        dir_.attributes = resolved_attrs

    # 2) ACTIONS — resolve to instances/inline models where appropriate
    for aid, air in mir.actions.items():
        action_cls = get_action(air.type_name)
        if not action_cls:
            logger.warning("resolve_symbols: action '%s' type '%s' not registered", aid, air.type_name)
            raise ResolverException(f"Action '{aid}' type '{air.type_name}' not registered")
        resolved_attrs = dict(air.attributes)
        for fname, ftype in _iter_model_fields(action_cls):
            if fname in resolved_attrs:
                resolved_attrs[fname] = _resolve_value_for_field(resolved_attrs[fname], ftype, mir.data)
        air.attributes = resolved_attrs

    # 3) EVENTS — same treatment as actions
    for ename, eir in mir.events.items():
        event_cls = get_event(eir.type_name)
        if not event_cls:
            logger.warning("resolve_symbols: event '%s' type '%s' not registered", ename, eir.type_name)
            raise ResolverException(f"Event '{ename}' type '{eir.type_name}' not registered")
        resolved_attrs = dict(eir.attributes)
        for fname, ftype in _iter_model_fields(event_cls):
            if fname in resolved_attrs:
                resolved_attrs[fname] = _resolve_value_for_field(resolved_attrs[fname], ftype, mir.data)
        eir.attributes = resolved_attrs

    logger.info("resolve_symbols: done")
    return mir

```
</details>

---
## <><code class="docs-class">class</code></> ResolverException

*Inherits from: <code>Exception</code>*


<details>
<summary>View Source</summary>
```python
class ResolverException(Exception):
    ...

```
</details>


---
