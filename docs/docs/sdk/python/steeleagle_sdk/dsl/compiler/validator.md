---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# validator

---

## <><code style={{color: '#13a6cf'}}>func</code></> validate_action

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def validate_action(type_name: str, attrs: Dict[str, Any]) -> Tuple[type[BaseModel], Dict[str, Any]]:
    logger.debug("validate_action: type=%s", type_name)
    cls = get_action(type_name)
    if cls is None:
        logger.warning("validate_action: unregistered action type '%s'", type_name)
        raise ValidatorException(f"Unregistered action type: {type_name}")
    model = _instantiate(cls, attrs)
    return cls, model.model_dump()

```
</details>

---
## <><code style={{color: '#13a6cf'}}>func</code></> validate_event

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def validate_event(type_name: str, attrs: Dict[str, Any]) -> Tuple[type[BaseModel], Dict[str, Any]]:
    logger.debug("validate_event: type=%s", type_name)
    cls = get_event(type_name)
    if cls is None:
        logger.warning("validate_event: unregistered event type '%s'", type_name)
        raise ValidatorException(f"Unregistered event type: {type_name}")
    model = _instantiate(cls, attrs)
    return cls, model.model_dump()

```
</details>

---
## <><code style={{color: '#13a6cf'}}>func</code></> validate_data

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def validate_data(type_name: str, attrs: Dict[str, Any]) -> Tuple[type[BaseModel], Dict[str, Any]]:
    logger.debug("validate_data: type=%s", type_name)
    cls = get_data(type_name)
    if cls is None:
        logger.warning("validate_data: unregistered data type '%s'", type_name)
        raise ValidatorException(f"Unregistered data type: {type_name}")
    model = _instantiate(cls, attrs)
    return cls, model.model_dump()

```
</details>

---
## <><code style={{color: '#13a6cf'}}>func</code></> validate_mission_ir

_Call Type: normal_


Validate and normalize every data, action, and event in the MissionIR.
Returns the same object with attributes replaced by normalized dumps.
<details>
<summary>View Source</summary>
```python
def validate_mission_ir(mir: MissionIR) -> MissionIR:
    """
    Validate and normalize every data, action, and event in the MissionIR.
    Returns the same object with attributes replaced by normalized dumps.
    """
    data_valid = 0
    actions_valid = 0
    events_valid = 0
    logger.info(
        "validator: start (data=%d, actions=%d, events=%d)",
        len(getattr(mir, "data", {})),
        len(mir.actions),
        len(mir.events),
    )

    # Data (validate first so downstream references are known-good)
    for did, dir_ in getattr(mir, "data", {}).items():
        try:
            _, normalized = validate_data(dir_.type_name, dir_.attributes)
            dir_.attributes = normalized
            data_valid += 1
        except ValidatorException as e:
            logger.error("validator: data '%s' (%s) invalid: %s", did, dir_.type_name, e)
            raise ValueError(
                f"Data '{did}' of type '{dir_.type_name}' failed validation: {e}"
            ) from e

    # Actions
    for aid, air in mir.actions.items():
        try:
            _, normalized = validate_action(air.type_name, air.attributes)
            air.attributes = normalized
            actions_valid += 1
        except ValidatorException as e:
            logger.error("validator: action '%s' (%s) invalid: %s", aid, air.type_name, e)
            raise ValueError(
                f"Action '{aid}' of type '{air.type_name}' failed validation: {e}"
            ) from e

    # Events
    for ename, eir in mir.events.items():
        try:
            _, normalized = validate_event(eir.type_name, eir.attributes)
            eir.attributes = normalized
            events_valid += 1
        except ValidatorException as e:
            logger.error("validator: event '%s' (%s) invalid: %s", ename, eir.type_name, e)
            raise ValueError(
                f"Event '{ename}' of type '{eir.type_name}' failed validation: {e}"
            ) from e

    logger.info(
        "validator: done (data_valid=%d, actions_valid=%d, events_valid=%d)",
        data_valid, actions_valid, events_valid
    )
    return mir

```
</details>

---
## <><code style={{color: '#b52ee6'}}>class</code></> ValidatorException

*Inherits from: <code>Exception</code>*

Compact error used at the DSL surface.


<details>
<summary>View Source</summary>
```python
class ValidatorException(Exception):
    """Compact error used at the DSL surface."""

```
</details>


---
