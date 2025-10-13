---
toc_max_heading_level: 2
---
# compositions

---

## <><code style={{color: '#b52ee6'}}>class</code></> AnyOf


Fires when ANY child event is true in a poll.


### <><code style={{color: '#10c45b'}}>method</code></> check


---
## <><code style={{color: '#b52ee6'}}>class</code></> AllOf


Fires when ALL child events are true in the same poll.


### <><code style={{color: '#10c45b'}}>method</code></> check


---
## <><code style={{color: '#b52ee6'}}>class</code></> Not


Fires when the child event is false (logical NOT).


### <><code style={{color: '#10c45b'}}>method</code></> check


---
## <><code style={{color: '#b52ee6'}}>class</code></> NOfM


Fires when at least N of M child events are true in a poll.


### <><code style={{color: '#10c45b'}}>method</code></> check


---
## <><code style={{color: '#b52ee6'}}>class</code></> Until


Fires when `event` becomes true BEFORE `until_event` becomes true.
If `until_event` fires first, this event will not fire (locks out) until
both are false again in the same poll (lock resets).


### <><code style={{color: '#10c45b'}}>method</code></> check


---
