---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';

# resolver

---

## <><code style={{color: '#13a6cf'}}>func</code></> resolve_symbols

_Call Type: normal_


Replace string IDs in attributes with *instances* of the referenced models
(not dicts). Works only for data. Also instantiates inline
data constructors present in action/event attributes.
<details>
<summary>View Source</summary>
```python
def resolve_symbols(mir: MissionIR) -> MissionIR:
    """
    Replace string IDs in attributes with *instances* of the referenced models
    (not dicts). Works only for data. Also instantiates inline
    data constructors present in action/event attributes.
    """
    logger.info(
        "resolve_symbols: start (actions=%d, events=%d, data=%d)",
        len(mir.actions), len(mir.events), len(mir.data)
    )

    # 1) DATA first
    for did, dir_ in mir.data.items():
        data_cls = get_data(dir_.type_name)
        if not data_cls:
            logger.warning("resolve_symbols: data '%s' type '%s' not registered", did, dir_.type_name)
            raise ResolverException(f"Data '{did}' type '{dir_.type_name}' not registered")
        resolved = dict(dir_.attributes)
        for fname, ftype in _iter_model_fields(data_cls):
            if fname in resolved:
                resolved[fname] = _resolve_value_for_field(resolved[fname], ftype, mir.data)
        dir_.attributes = resolved

    # 2) ACTIONS
    for aid, air in mir.actions.items():
        action_cls = get_action(air.type_name)
        if not action_cls:
            logger.warning("resolve_symbols: action '%s' type '%s' not registered", aid, air.type_name)
            raise ResolverException(f"Action '{aid}' type '{air.type_name}' not registered")
        resolved = dict(air.attributes)
        for fname, ftype in _iter_model_fields(action_cls):
            if fname in resolved:
                resolved[fname] = _resolve_value_for_field(resolved[fname], ftype, mir.data)
        air.attributes = resolved

    # 3) EVENTS
    for ename, eir in mir.events.items():
        event_cls = get_event(eir.type_name)
        if not event_cls:
            logger.warning("resolve_symbols: event '%s' type '%s' not registered", ename, eir.type_name)
            raise ResolverException(f"Event '{ename}' type '{eir.type_name}' not registered")
        resolved = dict(eir.attributes)
        for fname, ftype in _iter_model_fields(event_cls):
            if fname in resolved:
                resolved[fname] = _resolve_value_for_field(resolved[fname], ftype, mir.data)
        eir.attributes = resolved

    logger.info("resolve_symbols: done")
    return mir

```
</details>

---
## <><code style={{color: '#b52ee6'}}>class</code></> ResolverException



<details>
<summary>View Source</summary>
```python
class ResolverException(Exception): ...

```
</details>


---
