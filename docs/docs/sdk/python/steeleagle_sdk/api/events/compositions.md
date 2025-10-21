---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# compositions

---

## <><code style={{color: '#b52ee6'}}>class</code></> AnyOf

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-event">Event</Link></code>*

Fires when ANY child event is true in a poll.


### <><code style={{color: '#10c45b'}}>method</code></> check

_Call Type: async_


<details>
<summary>View Source</summary>
```python
@register_event
class AnyOf(Event):
    """Fires when ANY child event is true in a poll."""
    events: List[Event] = Field(..., min_items=1)

    async def check(self, context) -> bool:
        for ev in self.events:
            if await ev.check(context):
                return True
        return False

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> AllOf

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-event">Event</Link></code>*

Fires when ALL child events are true in the same poll.


### <><code style={{color: '#10c45b'}}>method</code></> check

_Call Type: async_


<details>
<summary>View Source</summary>
```python
@register_event
class AllOf(Event):
    """Fires when ALL child events are true in the same poll."""
    events: List[Event] = Field(..., min_items=1)

    async def check(self, context) -> bool:
        for ev in self.events:
            if not await ev.check(context):
                return False
        return True

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> Not

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-event">Event</Link></code>*

Fires when the child event is false (logical NOT).


### <><code style={{color: '#10c45b'}}>method</code></> check

_Call Type: async_


<details>
<summary>View Source</summary>
```python
@register_event
class Not(Event):
    """Fires when the child event is false (logical NOT)."""
    event: Event

    async def check(self, context) -> bool:
        return not (await self.event.check(context))

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> NOfM

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-event">Event</Link></code>*

Fires when at least N of M child events are true in a poll.


### <><code style={{color: '#10c45b'}}>method</code></> check

_Call Type: async_


<details>
<summary>View Source</summary>
```python
@register_event
class NOfM(Event):
    """Fires when at least N of M child events are true in a poll."""
    n: int = Field(..., gt=0)
    events: List[Event] = Field(..., min_items=1)

    async def check(self, context) -> bool:
        count = 0
        for ev in self.events:
            if await ev.check(context):
                count += 1
                if count >= self.n:
                    return True
        return False

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> Until

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-event">Event</Link></code>*

Fires when `event` becomes true BEFORE `until_event` becomes true.
If `until_event` fires first, this event will not fire (locks out) until
both are false again in the same poll (lock resets).


### <><code style={{color: '#10c45b'}}>method</code></> check

_Call Type: async_


<details>
<summary>View Source</summary>
```python
@register_event
class Until(Event):
    """
    Fires when `event` becomes true BEFORE `until_event` becomes true.
    If `until_event` fires first, this event will not fire (locks out) until
    both are false again in the same poll (lock resets).
    """
    event: Event
    until_event: Event
    _locked_out: bool = False

    async def check(self, context) -> bool:
        until_hit = await self.until_event.check(context)
        if until_hit:
            self._locked_out = True
            return False
        if self._locked_out:
            # reset lock when both are false in the same poll
            ev_now = await self.event.check(context)
            if not ev_now and not until_hit:
                self._locked_out = False
            return False
        return await self.event.check(context)

```
</details>


---
