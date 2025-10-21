---
toc_max_heading_level: 2
---

import Link from '@docusaurus/Link';
import { GoFileSymlinkFile } from "react-icons/go";

# singulars

---

## <><code style={{color: '#b52ee6'}}>class</code></> TimeReached

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-event">Event</Link></code>*


### <><code style={{color: '#10c45b'}}>method</code></> check

_Call Type: async_


Wait for a fixed duration; return True once reached.

<details>
<summary>View Source</summary>
```python
@register_event
class TimeReached(Event):
    duration: float = Field(..., ge=0.0, description="Seconds to wait before event triggers")

    async def check(self, context):
        """Wait for a fixed duration; return True once reached."""
        await asyncio.sleep(self.duration)
        return True

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> BatteryReached

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-event">Event</Link></code>*

Fires when battery percentage satisfies relation to threshold for N consecutive polls.
relation: `at_least` (greater than or equal to threshold) or `at_most` (less than or
equal to threshold).


### <><code style={{color: '#10c45b'}}>method</code></> check

_Call Type: async_


<details>
<summary>View Source</summary>
```python
@register_event
class BatteryReached(Event):
    '''
    Fires when battery percentage satisfies relation to threshold for N consecutive polls.
    relation: `at_least` (greater than or equal to threshold) or `at_most` (less than or
    equal to threshold).
    '''
    threshold: int = Field(..., ge=0, le=100)
    relation: Literal["at_least", "at_most"] = "at_most"
    consecutive: int = Field(1, ge=1)
    _streak: int = 0  # internal

    async def check(self, context) -> bool:
        tel = await context["data"].get_telemetry()
        bat = _get(tel, "battery")
        if not isinstance(bat, (int, float)):
            self._streak = 0
            return False
        ok = (bat >= self.threshold) if self.relation == "at_least" else (bat <= self.threshold)
        self._streak = (self._streak + 1) if ok else 0
        return self._streak >= self.consecutive

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> SatellitesReached

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-event">Event</Link></code>*

Fires when satellites count satisfies relation to threshold for N consecutive polls.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;relation**&nbsp;&nbsp;(<code>Literal['at_least', , , 'at_most']</code>) <text>&#8212;</text> `at_least` (greater than or equal to) or `at_most` (less than or equal to).



### <><code style={{color: '#10c45b'}}>method</code></> check

_Call Type: async_


<details>
<summary>View Source</summary>
```python
@register_event
class SatellitesReached(Event):
    """
    Fires when satellites count satisfies relation to threshold for N consecutive polls.

    Attributes:
        relation: `at_least` (greater than or equal to) or `at_most` (less than or equal to).
    """
    threshold: int = Field(..., ge=0)
    relation: Literal["at_least", "at_most"] = "at_least"
    consecutive: int = Field(1, ge=1)
    _streak: int = 0

    async def check(self, context) -> bool:
        tel = await context["data"].get_telemetry()
        sats = _get(tel, "satellites")
        if not isinstance(sats, (int, float)):
            self._streak = 0
            return False
        ok = (sats >= self.threshold) if self.relation == "at_least" else (sats <= self.threshold)
        self._streak = (self._streak + 1) if ok else 0
        return self._streak >= self.consecutive

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> GimbalPoseReached

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-event">Event</Link></code>*

Fires when gimbal pose matches target within tolerances.
You can specify any subset of `{roll, pitch, yaw}` (or x,y,z if your pose encodes axes).


### <><code style={{color: '#10c45b'}}>method</code></> check

_Call Type: async_


<details>
<summary>View Source</summary>
```python
@register_event
class GimbalPoseReached(Event):
    """
    Fires when gimbal pose matches target within tolerances.
    You can specify any subset of `{roll, pitch, yaw}` (or x,y,z if your pose encodes axes).
    """
    # target angles/axes (degrees or units your telemetry uses)
    roll: Optional[float] = None
    pitch: Optional[float] = None
    yaw: Optional[float] = None
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None

    # tolerances for each (defaults used when specific *_tol is None)
    tolerance: float = Field(1.0, ge=0.0)
    roll_tol: Optional[float] = None
    pitch_tol: Optional[float] = None
    yaw_tol: Optional[float] = None
    x_tol: Optional[float] = None
    y_tol: Optional[float] = None
    z_tol: Optional[float] = None

    def _within(self, cur: Optional[float], tgt: Optional[float], tol: Optional[float]) -> bool:
        if tgt is None:
            return True
        if cur is None:
            return False
        t = tol if tol is not None else self.tolerance
        return abs(cur - tgt) <= t

    async def check(self, context) -> bool:
        tel = await context["data"].get_telemetry()
        pose = _pose_components(tel)
        return (
            self._within(pose["roll"], self.roll, self.roll_tol) and
            self._within(pose["pitch"], self.pitch, self.pitch_tol) and
            self._within(pose["yaw"], self.yaw, self.yaw_tol) and
            self._within(pose["x"], self.x, self.x_tol) and
            self._within(pose["y"], self.y, self.y_tol) and
            self._within(pose["z"], self.z, self.z_tol)
        )

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> VelocityReached

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-event">Event</Link></code>*

Fires when speed magnitude in selected frame satisfies relation to threshold.
#### Attributes
**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;frame**&nbsp;&nbsp;(<code>Literal['enu', , , 'body']</code>) <text>&#8212;</text> `enu` or `body`

**<><code style={{color: '#e0a910'}}>attr</code></>&nbsp;&nbsp;relation**&nbsp;&nbsp;(<code>Literal['at_least', , , 'at_most']</code>) <text>&#8212;</text> `at_least` or `at_most`



### <><code style={{color: '#10c45b'}}>method</code></> check

_Call Type: async_


<details>
<summary>View Source</summary>
```python
@register_event
class VelocityReached(Event):
    """
    Fires when speed magnitude in selected frame satisfies relation to threshold.

    Attributes:
        frame: `enu` or `body`
        relation: `at_least` or `at_most`
    """
    frame: Literal["enu", "body"] = "enu"
    threshold: float = Field(..., gt=0.0)
    relation: Literal["at_least", "at_most"] = "at_least"

    async def check(self, context) -> bool:
        tel = await context["data"].get_telemetry()
        spd = _speed_mag(tel, self.frame)
        if spd is None:
            return False
        return spd >= self.threshold if self.relation == "at_least" else spd <= self.threshold

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> HomeReached

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-event">Event</Link></code>*

Fires when distance from current `global_position` to home less than or equal to `radius_m` (meters).
Requires `global_position.{latitude, longitude}` and `home.{latitude, longitude}`.


### <><code style={{color: '#10c45b'}}>method</code></> check

_Call Type: async_


<details>
<summary>View Source</summary>
```python
@register_event
class HomeReached(Event):
    """
    Fires when distance from current `global_position` to home less than or equal to `radius_m` (meters).
    Requires `global_position.{latitude, longitude}` and `home.{latitude, longitude}`.
    """
    radius_m: float = Field(..., gt=0.0)

    async def check(self, context) -> bool:
        tel = await context["data"].get_telemetry()
        lat = _get(tel, "global_position", "latitude")
        lon = _get(tel, "global_position", "longitude")
        hlat = _get(tel, "home", "latitude")
        hlon = _get(tel, "home", "longitude")
        if not all(isinstance(v, (int, float)) for v in (lat, lon, hlat, hlon)):
            return False
        d = _haversine_m(float(lat), float(lon), float(hlat), float(hlon))
        return d <= self.radius_m

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> DetectionFound

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-event">Event</Link></code>*


### <><code style={{color: '#10c45b'}}>method</code></> check

_Call Type: async_


<details>
<summary>View Source</summary>
```python
@register_event
class DetectionFound(Event):
    """
    Fires when any detection matches optional filters:
      - `class_name` (case-insensitive) if provided
      - `min_score` greater than of equal to threshold if provided
    """
    compute_type: str = Field(..., min_length=1)
    target: Optional[str] = Field(None)
    min_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    async def check(self, context) -> bool:
        results = await context["data"].get_compute_result(self.compute_type)
        dets = _extract_detections(results)
        if not dets:
            return False

        want_class = self.class_name.lower() if isinstance(self.class_name, str) else None
        for d in dets:
            cls = d.get("class_name")
            scr = d.get("score")
            if want_class is not None and (not isinstance(cls, str) or cls.lower() != want_class):
                continue
            if self.min_score is not None:
                try:
                    if float(scr) < float(self.min_score):
                        continue
                except Exception:
                    continue
            return True
        return False

```
</details>


---
## <><code style={{color: '#b52ee6'}}>class</code></> HSVReached

*Inherits from: <code><Link to="/sdk/python/steeleagle_sdk/api/base#class-event">Event</Link></code>*

Fires when any detection indicates HSV filter passed (boolean flag).
Optional filters: `class_name`, `min_score`.
Assumes detection dicts may have `hsv_filter_passed`: bool.


### <><code style={{color: '#10c45b'}}>method</code></> check

_Call Type: async_


<details>
<summary>View Source</summary>
```python
@register_event
class HSVReached(Event):
    """
    Fires when any detection indicates HSV filter passed (boolean flag).
    Optional filters: `class_name`, `min_score`.
    Assumes detection dicts may have `hsv_filter_passed`: bool.
    """
    compute_type: str = Field(..., min_length=1)
    class_name: Optional[str] = Field(None)
    min_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    async def check(self, context) -> bool:
        results = await context["data"].get_compute_result(self.compute_type)
        dets = _extract_detections(results)
        if not dets:
            return False

        want_class = self.class_name.lower() if isinstance(self.class_name, str) else None
        for d in dets:
            if not d.get("hsv_filter_passed", False):
                continue
            cls = d.get("class_name")
            scr = d.get("score")
            if want_class is not None and (not isinstance(cls, str) or cls.lower() != want_class):
                continue
            if self.min_score is not None:
                try:
                    if float(scr) < float(self.min_score):
                        continue
                except Exception:
                    continue
            return True
        return False

```
</details>


---
