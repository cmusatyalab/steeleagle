---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# base

---

## <><code style={{color: '#b52ee6'}}>class</code></> Action

*Inherits from: <code>pydantic.BaseModel</code>*

Pydantic base model for actions (things you execute).


### <><code style={{color: '#10c45b'}}>method</code></> execute

_Call Type: async_


Execute the action asynchronously.

<details>
<summary>View Source</summary>
```python
class Action(BaseModel):
    '''
    Pydantic base model for actions (things you execute).
    '''
    # Lenient validation; allow non-pydantic objects in fields if needed
    model_config = ConfigDict(extra='forbid', arbitrary_types_allowed=True, ignored_types=(type(Enum),))

    async def execute(self) -> Any:
        '''
        Execute the action asynchronously.
        '''
        raise NotImplementedError

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> Event

*Inherits from: <code>pydantic.BaseModel</code>*

Pydantic base model for events (things you wait/observe).


### <><code style={{color: '#10c45b'}}>method</code></> check

_Call Type: async_


Check to see if the event has been completed.

<details>
<summary>View Source</summary>
```python
class Event(BaseModel):
    '''
    Pydantic base model for events (things you wait/observe).
    '''
    # Lenient validation; allow non-pydantic objects in fields if needed
    model_config = ConfigDict(extra='forbid', arbitrary_types_allowed=True, ignored_types=(type(Enum),))

    async def check(self) -> bool:
        '''
        Check to see if the event has been completed.
        '''
        raise NotImplementedError

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> Datatype

*Inherits from: <code>pydantic.BaseModel</code>*

Pydantic base model for a Protobuf message.


<details>
<summary>View Source</summary>
```python
class Datatype(BaseModel):
    '''
    Pydantic base model for a Protobuf message.
    '''
    # Lenient validation; allow non-pydantic objects in fields if needed
    model_config = ConfigDict(extra='forbid', arbitrary_types_allowed=True, ignored_types=(type(Enum),))

```
</details>


---
