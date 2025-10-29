---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# registry

---

## <><code class="docs-func">func</code></> register_action

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def register_action(cls: Action) -> Action:
    key = _norm(cls.__name__)
    prev = _ACTIONS.get(key)
    _ACTIONS[key] = cls
    if prev and prev is not cls:
        logger.warning("Overwriting action '%s'", key)
    else:
        logger.info("Registered action '%s'", key)
    return cls

```
</details>

---
## <><code class="docs-func">func</code></> register_event

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def register_event(cls: Event) -> Event:
    key = _norm(cls.__name__)
    prev = _EVENTS.get(key)
    _EVENTS[key] = cls
    if prev and prev is not cls:
        logger.warning("Overwriting event '%s'", key)
    else:
        logger.info("Registered event '%s'", key)
    return cls

```
</details>

---
## <><code class="docs-func">func</code></> register_data

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def register_data(cls: Datatype) -> Datatype:
    key = _norm(cls.__name__)
    prev = _DATA.get(key)
    _DATA[key] = cls
    if prev and prev is not cls:
        logger.warning("Overwriting message '%s'", key)
    else:
        logger.info("Registered message '%s'", key)
    return cls

```
</details>

---
## <><code class="docs-func">func</code></> get_action

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def get_action(name: str) -> Optional[Action]:
    return _ACTIONS.get(_norm(name))

```
</details>

---
## <><code class="docs-func">func</code></> get_event

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def get_event(name: str) -> Optional[Event]:
    return _EVENTS.get(_norm(name))

```
</details>

---
## <><code class="docs-func">func</code></> get_data

_Call Type: normal_

<details>
<summary>View Source</summary>
```python
def get_data(name: str) -> Optional[Datatype]:
    return _DATA.get(_norm(name))

```
</details>

---
