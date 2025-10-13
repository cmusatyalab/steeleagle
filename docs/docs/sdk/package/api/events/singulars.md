---
toc_max_heading_level: 2
---
# singulars

---

## <><code style={{color: '#b52ee6'}}>class</code></> TimeReached



### <><code style={{color: '#10c45b'}}>method</code></> check


Wait for a fixed duration; return True once reached.

---
## <><code style={{color: '#b52ee6'}}>class</code></> BatteryReached


Fires when battery percentage satisfies relation to threshold for N consecutive polls.
relation: `at_least` (greater than or equal to threshold) or `at_most` (less than or
equal to threshold).


### <><code style={{color: '#10c45b'}}>method</code></> check


---
## <><code style={{color: '#b52ee6'}}>class</code></> SatellitesReached


Fires when satellites count satisfies relation to threshold for N consecutive polls.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> relation** (`Literal['at_least', 'at_most']`) <text>&#8212;</text> `at_least` (greater than or equal to) or `at_most` (less than or equal to).



### <><code style={{color: '#10c45b'}}>method</code></> check


---
## <><code style={{color: '#b52ee6'}}>class</code></> GimbalPoseReached


Fires when gimbal pose matches target within tolerances.
You can specify any subset of `{roll, pitch, yaw}` (or x,y,z if your pose encodes axes).


### <><code style={{color: '#10c45b'}}>method</code></> check


---
## <><code style={{color: '#b52ee6'}}>class</code></> VelocityReached


Fires when speed magnitude in selected frame satisfies relation to threshold.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></> frame** (`Literal['enu', 'body']`) <text>&#8212;</text> `enu` or `body`

**<><code style={{color: '#e0a910'}}>attr</code></> relation** (`Literal['at_least', 'at_most']`) <text>&#8212;</text> `at_least` or `at_most`



### <><code style={{color: '#10c45b'}}>method</code></> check


---
## <><code style={{color: '#b52ee6'}}>class</code></> HomeReached


Fires when distance from current `global_position` to home less than or equal to `radius_m` (meters).
Requires `global_position.{latitude, longitude}` and `home.{latitude, longitude}`.


### <><code style={{color: '#10c45b'}}>method</code></> check


---
## <><code style={{color: '#b52ee6'}}>class</code></> DetectionFound



### <><code style={{color: '#10c45b'}}>method</code></> check


---
## <><code style={{color: '#b52ee6'}}>class</code></> HSVReached


Fires when any detection indicates HSV filter passed (boolean flag).
Optional filters: `class_name`, `min_score`.
Assumes detection dicts may have `hsv_filter_passed`: bool.


### <><code style={{color: '#10c45b'}}>method</code></> check


---
