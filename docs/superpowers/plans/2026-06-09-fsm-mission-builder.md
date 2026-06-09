# FSM Mission Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the placeholder PlanPage with a drag-and-drop FSM editor that compiles missions via the Python backend and deploys them to vehicles.

**Architecture:** The frontend (React + `@xyflow/react`) provides a task palette, canvas, and deploy toolbar. Two new FastAPI endpoints (`GET /api/schema`, `POST /api/compile`) introspect the installed SteelEagle SDK's Pydantic models and compile graph state into `mission.json`. The frontend uses `tokml` to convert GeoJSON map features to KML before calling the existing `/api/upload` endpoint.

**Tech Stack:** React 19, `@xyflow/react` 12 (already installed), PrimeReact `TabView`/`Dialog`/`Sidebar`, `tokml` (new npm dep), FastAPI, `steeleagle_sdk` (local path), `pydantic`, `dataclasses.asdict`, `pytest`, `fastapi.testclient`

---

## File Map

| Action | Path | Purpose |
|---|---|---|
| Modify | `gcs/react/backend/pyproject.toml` | Switch SDK to local path dep |
| Modify | `gcs/react/backend/app/api.py` | Add `/api/schema` + `/api/compile` routes |
| Create | `gcs/react/backend/tests/__init__.py` | Make tests a package |
| Create | `gcs/react/backend/tests/test_schema.py` | Tests for `/api/schema` |
| Create | `gcs/react/backend/tests/test_compile.py` | Tests for `/api/compile` |
| Modify | `gcs/react/prime/package.json` | Add `tokml` dependency |
| Modify | `gcs/react/prime/src/PlanPage.jsx` | Full restructure into tabbed layout |
| Modify | `gcs/react/prime/src/MapDraw.jsx` | Add per-feature name input |
| Create | `gcs/react/prime/src/TaskNode.jsx` | Custom RF node: icon + name + key params |
| Create | `gcs/react/prime/src/TaskNodePanel.jsx` | Slide-in panel for nodes with >3 fields |
| Create | `gcs/react/prime/src/FsmPalette.jsx` | Draggable action palette + event reference |
| Create | `gcs/react/prime/src/ConnectModal.jsx` | Modal for labelling new edges with events |
| Modify | `gcs/react/prime/src/App.jsx` | Pass `squadList`/`vehicles` to PlanPage |

---

## Task 1: Switch backend to local SDK

The PyPI `steeleagle_sdk` 1.0.16 is missing its grammar file, which causes an import error the moment any `dsl.*` submodule is touched. The local SDK at `sdk/` (v3.1.0) has all files. Point the backend's venv at the local copy.

**Files:**
- Modify: `gcs/react/backend/pyproject.toml`

- [ ] **Step 1: Add uv path source to pyproject.toml**

Open `gcs/react/backend/pyproject.toml`. The full file after the change (keep all existing deps, only add the `[tool.uv.sources]` block and change nothing else):

```toml
[project]
name = "gcs"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "pydantic",
    "pydantic-extra-types",
    "zmq",
    "grpcio>=1.74.0",
    "toml",
    "redis",
    "fastapi",
    "uvicorn",
    "steeleagle_sdk",
    "websockets",
    "rich",
    "opencv-python",
    "numpy",
    "colorhash",
]

[tool.uv.sources]
steeleagle_sdk = { path = "../../../sdk", editable = true }
```

- [ ] **Step 2: Re-sync the venv**

```bash
cd gcs/react/backend
uv sync
```

Expected: output contains `steeleagle-sdk` resolved from local path with no errors.

- [ ] **Step 3: Verify the DSL modules import cleanly**

```bash
cd gcs/react/backend
.venv/bin/python -c "
from steeleagle_sdk.dsl.compiler.loader import load_all
from steeleagle_sdk.dsl.compiler.registry import _ACTIONS, _EVENTS
load_all()
print('actions:', sorted(_ACTIONS.keys()))
print('events:', sorted(_EVENTS.keys()))
"
```

Expected: prints lists of action names (patrol, track, takeoff, etc.) and event names (batteryreached, detectionfound, etc.) with no errors.

- [ ] **Step 4: Commit**

```bash
git add gcs/react/backend/pyproject.toml gcs/react/backend/uv.lock
git commit -m "feat: switch gcs backend to local sdk path dependency"
```

---

## Task 2: Backend `GET /api/schema`

Add a route that introspects all registered Pydantic action/event classes and returns their field metadata. Extract the route logic into a pure helper so it can be tested without starting the full app.

**Files:**
- Modify: `gcs/react/backend/app/api.py`
- Create: `gcs/react/backend/tests/__init__.py`
- Create: `gcs/react/backend/tests/test_schema.py`

- [ ] **Step 1: Write the failing test**

Create `gcs/react/backend/tests/__init__.py` (empty):
```python
```

Create `gcs/react/backend/tests/test_schema.py`:
```python
import pytest
from app.api import build_schema_response


def test_schema_has_actions_and_events():
    schema = build_schema_response()
    assert "actions" in schema
    assert "events" in schema
    assert len(schema["actions"]) > 0
    assert len(schema["events"]) > 0


def test_schema_action_has_fields():
    schema = build_schema_response()
    # Patrol is always registered
    assert "Patrol" in schema["actions"]
    patrol = schema["actions"]["Patrol"]
    assert "description" in patrol
    assert "fields" in patrol
    field_names = [f["name"] for f in patrol["fields"]]
    assert "hover_time" in field_names
    assert "waypoints" in field_names


def test_schema_field_has_required_keys():
    schema = build_schema_response()
    for type_name, entry in schema["actions"].items():
        for field in entry["fields"]:
            assert "name" in field, f"{type_name} field missing 'name'"
            assert "type" in field, f"{type_name}.{field.get('name')} missing 'type'"
            assert "required" in field, f"{type_name}.{field.get('name')} missing 'required'"


def test_schema_waypoints_field_has_object_type():
    schema = build_schema_response()
    patrol_fields = {f["name"]: f for f in schema["actions"]["Patrol"]["fields"]}
    assert patrol_fields["waypoints"]["type"] == "object"
    assert patrol_fields["waypoints"].get("object_type") == "Waypoints"


def test_schema_event_detectionfound():
    schema = build_schema_response()
    assert "DetectionFound" in schema["events"]
    df = schema["events"]["DetectionFound"]
    assert "fields" in df
    field_names = [f["name"] for f in df["fields"]]
    assert "target" in field_names
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd gcs/react/backend
.venv/bin/pytest tests/test_schema.py -v
```

Expected: `ImportError` or `AttributeError` — `build_schema_response` does not exist yet.

- [ ] **Step 3: Implement `build_schema_response` and the route**

Add the following imports at the top of `gcs/react/backend/app/api.py`, after the existing imports:

```python
from steeleagle_sdk.dsl.compiler.loader import load_all as _dsl_load_all
from steeleagle_sdk.dsl.compiler.registry import _ACTIONS, _EVENTS
```

Add the helper and route anywhere before the `app.mount` line at the bottom of `api.py`:

```python
def _resolve_ref(prop: dict, defs: dict) -> dict:
    """Follow a single $ref pointer in a JSON Schema fragment."""
    if "$ref" in prop:
        ref_name = prop["$ref"].split("/")[-1]
        return defs.get(ref_name, prop)
    return prop


def _unwrap_anyof(prop: dict) -> dict:
    """Unwrap anyOf that represents an Optional type (drop the null branch)."""
    if "anyOf" in prop:
        non_null = [t for t in prop["anyOf"] if t.get("type") != "null"]
        return non_null[0] if non_null else prop
    return prop


def _extract_fields(cls) -> list[dict]:
    """Return a flat field list from a Pydantic model class."""
    schema = cls.model_json_schema()
    defs = schema.get("$defs", {})
    properties = schema.get("properties", {})
    required_set = set(schema.get("required", []))

    fields = []
    for name, raw_prop in properties.items():
        prop = _resolve_ref(raw_prop, defs)
        prop = _unwrap_anyof(prop)
        prop = _resolve_ref(prop, defs)  # resolve after unwrapping

        field_type = prop.get("type", "object")
        # Treat anything that still lacks a scalar type as object
        if field_type not in ("string", "number", "integer", "boolean", "array"):
            field_type = "object"

        entry: dict = {
            "name": name,
            "type": field_type,
            "required": name in required_set,
            "description": raw_prop.get("description", prop.get("description", "")),
        }
        # Propagate default if present on the raw property (Pydantic puts it there)
        if "default" in raw_prop:
            entry["default"] = raw_prop["default"]

        # Tag Waypoints objects so the frontend can show the area dropdown
        if field_type == "object":
            ref_raw = raw_prop if "$ref" in raw_prop else (
                next((t for t in raw_prop.get("anyOf", []) if "$ref" in t), {})
            )
            ref_name = ref_raw.get("$ref", "").split("/")[-1]
            if ref_name:
                entry["object_type"] = ref_name

        fields.append(entry)

    return fields


def build_schema_response() -> dict:
    """Pure function — safe to call from tests without the full app running."""
    _dsl_load_all()
    result: dict = {"actions": {}, "events": {}}
    for type_name, cls in _ACTIONS.items():
        display = cls.__name__  # original CamelCase name
        result["actions"][display] = {
            "description": (cls.__doc__ or "").strip().splitlines()[0] if cls.__doc__ else "",
            "fields": _extract_fields(cls),
        }
    for type_name, cls in _EVENTS.items():
        display = cls.__name__
        result["events"][display] = {
            "description": (cls.__doc__ or "").strip().splitlines()[0] if cls.__doc__ else "",
            "fields": _extract_fields(cls),
        }
    return result


@app.get("/api/schema")
async def get_schema():
    return build_schema_response()
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
cd gcs/react/backend
.venv/bin/pytest tests/test_schema.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gcs/react/backend/app/api.py gcs/react/backend/tests/
git commit -m "feat: add GET /api/schema endpoint"
```

---

## Task 3: Backend `POST /api/compile`

Add a route that validates the graph state, builds a `MissionIR`, and returns `mission.json` JSON. Validation uses Pydantic — instantiating each action/event class with its `params` dict triggers type-checking for free.

**Files:**
- Modify: `gcs/react/backend/app/api.py`
- Create: `gcs/react/backend/tests/test_compile.py`

- [ ] **Step 1: Write the failing test**

Create `gcs/react/backend/tests/test_compile.py`:

```python
import pytest
from pydantic import ValidationError
from app.api import compile_mission, CompileRequest, CompileNode, CompileEvent, CompileEdge


def _minimal_request():
    return CompileRequest(
        nodes=[CompileNode(instance_id="take_off", type_name="TakeOff", params={"take_off_altitude": 10.0})],
        events=[],
        edges=[],
        start_id="take_off",
    )


def test_compile_minimal_mission():
    result = compile_mission(_minimal_request())
    assert "mission" in result
    mission = result["mission"]
    assert mission["start_action_id"] == "take_off"
    assert "take_off" in mission["actions"]
    assert mission["actions"]["take_off"]["type_name"] == "TakeOff"


def test_compile_transitions():
    req = CompileRequest(
        nodes=[
            CompileNode(instance_id="take_off", type_name="TakeOff", params={"take_off_altitude": 10.0}),
            CompileNode(instance_id="patrol", type_name="Patrol", params={
                "waypoints": {"area": "AreaB", "alt": 15.0, "algo": "edge"}
            }),
        ],
        events=[],
        edges=[
            CompileEdge(source="take_off", event_id="done", target="patrol"),
            CompileEdge(source="patrol", event_id="done", target="patrol"),  # self-loop
        ],
        start_id="take_off",
    )
    result = compile_mission(req)
    assert result["mission"]["transitions"]["take_off"]["done"] == "patrol"
    assert result["mission"]["transitions"]["patrol"]["done"] == "patrol"


def test_compile_with_events():
    req = CompileRequest(
        nodes=[
            CompileNode(instance_id="patrol", type_name="Patrol", params={
                "waypoints": {"area": "AreaB", "alt": 15.0, "algo": "edge"}
            }),
            CompileNode(instance_id="track", type_name="Track", params={
                "target": {"class_name": "person", "score": 60.0}
            }),
        ],
        events=[
            CompileEvent(instance_id="person_seen", type_name="DetectionFound",
                         params={"target": {"class_name": "person", "score": 60.0}}),
        ],
        edges=[
            CompileEdge(source="patrol", event_id="person_seen", target="track"),
        ],
        start_id="patrol",
    )
    result = compile_mission(req)
    assert "person_seen" in result["mission"]["events"]
    assert result["mission"]["transitions"]["patrol"]["person_seen"] == "track"


def test_compile_unknown_type_name_returns_error():
    req = CompileRequest(
        nodes=[CompileNode(instance_id="foo", type_name="DoesNotExist", params={})],
        events=[],
        edges=[],
        start_id="foo",
    )
    result = compile_mission(req)
    assert "errors" in result
    assert any("DoesNotExist" in e["message"] for e in result["errors"])


def test_compile_invalid_params_returns_error():
    req = CompileRequest(
        nodes=[CompileNode(instance_id="take_off", type_name="TakeOff",
                           params={"take_off_altitude": "not_a_number"})],
        events=[],
        edges=[],
        start_id="take_off",
    )
    result = compile_mission(req)
    assert "errors" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd gcs/react/backend
.venv/bin/pytest tests/test_compile.py -v
```

Expected: `ImportError` — `compile_mission`, `CompileRequest` etc. don't exist yet.

- [ ] **Step 3: Implement the request models and route**

In `gcs/react/backend/app/api.py`, add the following imports at the top (alongside the existing ones):

```python
from dataclasses import asdict
from steeleagle_sdk.dsl.compiler.ir import ActionIR, EventIR, DatumIR, MissionIR
from steeleagle_sdk.dsl.compiler.registry import get_action, get_event
```

Add the request models and handler anywhere before the `app.mount` line:

```python
class CompileNode(BaseModel):
    instance_id: str
    type_name: str
    params: dict = {}


class CompileEvent(BaseModel):
    instance_id: str
    type_name: str
    params: dict = {}


class CompileEdge(BaseModel):
    source: str
    event_id: str
    target: str


class CompileRequest(BaseModel):
    nodes: list[CompileNode]
    events: list[CompileEvent]
    edges: list[CompileEdge]
    start_id: str


def compile_mission(request: CompileRequest) -> dict:
    """Pure function — safe to call from tests without the full app running."""
    from pydantic import ValidationError

    _dsl_load_all()
    errors: list[dict] = []

    # Validate all type_names exist and params are valid
    for node in request.nodes:
        cls = get_action(node.type_name)
        if cls is None:
            errors.append({"node_id": node.instance_id,
                           "message": f"Unknown action type: {node.type_name}"})
            continue
        try:
            cls(**node.params)
        except (ValidationError, TypeError) as exc:
            errors.append({"node_id": node.instance_id, "message": str(exc)})

    for ev in request.events:
        cls = get_event(ev.type_name)
        if cls is None:
            errors.append({"node_id": ev.instance_id,
                           "message": f"Unknown event type: {ev.type_name}"})
            continue
        try:
            cls(**ev.params)
        except (ValidationError, TypeError) as exc:
            errors.append({"node_id": ev.instance_id, "message": str(exc)})

    if errors:
        return {"errors": errors}

    # Build MissionIR
    actions = {
        n.instance_id: ActionIR(
            type_name=n.type_name,
            action_id=n.instance_id,
            attributes=n.params,
        )
        for n in request.nodes
    }
    events = {
        e.instance_id: EventIR(
            type_name=e.type_name,
            event_id=e.instance_id,
            attributes=e.params,
        )
        for e in request.events
    }

    transitions: dict[str, dict[str, str]] = {}
    for edge in request.edges:
        transitions.setdefault(edge.source, {})[edge.event_id] = edge.target

    mission_ir = MissionIR(
        actions=actions,
        events=events,
        data={},
        start_action_id=request.start_id,
        transitions=transitions,
    )
    return {"mission": asdict(mission_ir)}


@app.post("/api/compile")
async def compile_mission_route(request: CompileRequest) -> dict:
    return compile_mission(request)
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
cd gcs/react/backend
.venv/bin/pytest tests/test_compile.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gcs/react/backend/app/api.py gcs/react/backend/tests/test_compile.py
git commit -m "feat: add POST /api/compile endpoint"
```

---

## Task 4: Frontend — install `tokml` and restructure `PlanPage` tabs

Replace the current single-panel `PlanPage` with a PrimeReact `TabView` containing three tabs. Move `MapDraw` to the Map tab. The FSM Builder and JSON Output tabs are wired up in later tasks; here we just establish the shell.

**Files:**
- Modify: `gcs/react/prime/package.json`
- Modify: `gcs/react/prime/src/PlanPage.jsx`

- [ ] **Step 1: Add `tokml` to package.json**

In `gcs/react/prime/package.json`, add `"tokml": "^0.4.0"` to `dependencies`:

```json
{
  "name": "prime",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "lint": "eslint .",
    "preview": "vite preview"
  },
  "dependencies": {
    "@mapbox/mapbox-gl-draw": "^1.5.1",
    "@microsoft/fetch-event-source": "^2.0.1",
    "@xyflow/react": "^12.10.0",
    "chart.js": "^4.5.1",
    "color-hash": "^2.0.2",
    "mapbox-gl": "^3.17.0",
    "primeflex": "^4.0.0",
    "primeicons": "^7.0.0",
    "primereact": "^10.9.7",
    "quill": "^2.0.2",
    "react": "^19.2.1",
    "react-dom": "^19.2.1",
    "react-gamepad-tl": "^1.0.1",
    "react-use-websocket": "^4.13.0",
    "tokml": "^0.4.0"
  },
  "devDependencies": {
    "@eslint/js": "^9.39.1",
    "@types/react": "^19.2.5",
    "@types/react-dom": "^19.2.3",
    "@vitejs/plugin-react": "^5.1.1",
    "eslint": "^9.39.1",
    "eslint-plugin-react-hooks": "^7.0.1",
    "eslint-plugin-react-refresh": "^0.4.24",
    "globals": "^16.5.0",
    "vite": "^7.2.4"
  }
}
```

- [ ] **Step 2: Install the new dependency**

```bash
cd gcs/react/prime
npm install
```

Expected: `node_modules/tokml/` is present, no errors.

- [ ] **Step 3: Rewrite PlanPage with tab shell**

Replace `gcs/react/prime/src/PlanPage.jsx` entirely:

```jsx
import { useState, useCallback } from 'react'
import { TabView, TabPanel } from 'primereact/tabview';
import { Background, Controls, MiniMap, ReactFlow,
         applyNodeChanges, applyEdgeChanges } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import MapDraw from './MapDraw.jsx';
import { InputTextarea } from 'primereact/inputtextarea';

function PlanPage({ vehicles, squadList }) {
    const [nodes, setNodes] = useState([]);
    const [edges, setEdges] = useState([]);
    const [eventInstances, setEventInstances] = useState([]);
    const [startNodeId, setStartNodeId] = useState(null);
    const [schema, setSchema] = useState({ actions: {}, events: {} });
    const [compiledMission, setCompiledMission] = useState(null);
    const [features, setFeatures] = useState(JSON.stringify({ type: 'FeatureCollection', features: [] }));

    const onNodesChange = useCallback(
        (changes) => setNodes((ns) => applyNodeChanges(changes, ns)), []);
    const onEdgesChange = useCallback(
        (changes) => setEdges((es) => applyEdgeChanges(changes, es)), []);

    return (
        <TabView className="h-full">
            <TabPanel header="FSM Builder" leftIcon="pi pi-share-alt mr-2">
                <div className="flex" style={{ height: 'calc(100vh - 180px)' }}>
                    {/* Palette placeholder — filled in Task 7 */}
                    <div style={{ width: 180, background: '#1e2a38', flexShrink: 0 }}>
                        <p className="p-2 text-sm text-color-secondary">Palette loading...</p>
                    </div>
                    {/* Canvas */}
                    <div className="flex-1" style={{ position: 'relative' }}>
                        <ReactFlow
                            colorMode="dark"
                            nodes={nodes}
                            edges={edges}
                            onNodesChange={onNodesChange}
                            onEdgesChange={onEdgesChange}
                            fitView
                        >
                            <Controls />
                            <MiniMap />
                            <Background variant="dots" gap={12} size={1} />
                        </ReactFlow>
                    </div>
                </div>
                {/* Toolbar placeholder — filled in Task 10 */}
                <div className="flex gap-2 p-2" style={{ borderTop: '1px solid #2a3a4a' }}>
                    <span className="text-sm text-color-secondary">
                        {nodes.length} actions · {eventInstances.length} events
                        {startNodeId ? ` · start: ${nodes.find(n => n.id === startNodeId)?.data?.instance_id ?? startNodeId}` : ' · ⚠ no start set'}
                    </span>
                </div>
            </TabPanel>

            <TabPanel header="Map" leftIcon="pi pi-map mr-2">
                <div style={{ height: 'calc(100vh - 180px)' }}>
                    <MapDraw features={features} setFeatures={setFeatures} />
                </div>
            </TabPanel>

            <TabPanel header="JSON Output" leftIcon="pi pi-code mr-2">
                <InputTextarea
                    className="w-full h-full"
                    style={{ height: 'calc(100vh - 200px)', fontFamily: 'monospace', fontSize: 12 }}
                    readOnly
                    value={compiledMission ? JSON.stringify(compiledMission, null, 2) : '// compile a mission to see output'}
                />
            </TabPanel>
        </TabView>
    );
}

export default PlanPage;
```

- [ ] **Step 4: Update App.jsx to pass props to PlanPage**

In `gcs/react/prime/src/App.jsx`, find the line:
```jsx
{selectedMenu == "Plan" && <PlanPage />}
```

Replace it with:
```jsx
{selectedMenu == "Plan" && <PlanPage vehicles={vehicles} squadList={squadList} />}
```

- [ ] **Step 5: Verify the tabs render**

```bash
cd gcs/react/prime
npm run dev
```

Open the app, click the Plan menu item. You should see three tabs: FSM Builder, Map, JSON Output. The Map tab should show the Mapbox map. The FSM Builder shows an empty React Flow canvas and "Palette loading..." text.

- [ ] **Step 6: Commit**

```bash
cd gcs/react/prime && npm run build
git add gcs/react/prime/src/PlanPage.jsx gcs/react/prime/src/App.jsx gcs/react/prime/package.json gcs/react/prime/package-lock.json
git commit -m "feat: restructure PlanPage into tabbed layout"
```

---

## Task 5: MapDraw feature naming

When a polygon or line is drawn or selected, show a text input that lets the user assign a name. The name is stored in `feature.properties.name` and flows up through the existing `features` / `setFeatures` state.

**Files:**
- Modify: `gcs/react/prime/src/MapDraw.jsx`

- [ ] **Step 1: Rewrite MapDraw with naming support**

Replace `gcs/react/prime/src/MapDraw.jsx` entirely:

```jsx
import { useState, useRef, useEffect, useCallback } from 'react'
import mapboxgl from 'mapbox-gl';
import MapboxDraw from '@mapbox/mapbox-gl-draw';
import 'mapbox-gl/dist/mapbox-gl.css';
import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';
import { MAPBOX_TOKEN } from './config.js';
import ColorHash from 'color-hash'
import { InputText } from 'primereact/inputtext';
import { Button } from 'primereact/button';

function MapDraw({ features, setFeatures }) {
    const mapRef = useRef();
    const mapContainerRef = useRef();
    const draw = useRef();
    const numFeaturesRef = useRef(0);
    const colorHash = new ColorHash();

    // Selected feature for naming
    const [selectedFeatureId, setSelectedFeatureId] = useState(null);
    const [nameInput, setNameInput] = useState('');

    // Parse features to object once
    const featuresObj = typeof features === 'string' ? JSON.parse(features) : features;

    const pushFeatures = useCallback(() => {
        const data = draw.current.getAll();
        setFeatures(JSON.stringify(data));
    }, [setFeatures]);

    useEffect(() => {
        mapboxgl.accessToken = `${MAPBOX_TOKEN}`;
        mapRef.current = new mapboxgl.Map({
            container: mapContainerRef.current,
            style: 'mapbox://styles/mapbox/standard',
            center: [-79.94299, 40.44353],
            zoom: 13.03,
            config: {
                basemap: {
                    lightPreset: 'day',
                    showPedestrianRoads: false,
                    showPointOfInterestLabels: false,
                    showTransitLabels: false,
                    showAdminBoundaries: false,
                    font: 'Montserrat',
                }
            },
        });

        mapRef.current.on('style.load', () => {
            mapRef.current.addSource('mapbox-dem', {
                type: 'raster-dem',
                url: 'mapbox://mapbox.mapbox-terrain-dem-v1',
                tileSize: 512,
                maxzoom: 14,
            });
            mapRef.current.setTerrain({ source: 'mapbox-dem', exaggeration: 1.0 });
            mapRef.current.addControl(new mapboxgl.NavigationControl());
        });

        draw.current = new MapboxDraw({ displayControlsDefault: true, defaultMode: 'draw_polygon' });
        mapRef.current.addControl(draw.current);

        function updateFeatures(e) {
            let temp = draw.current.get(e.features[0].id);
            temp.id = e.features[0].geometry.type + '-' + numFeaturesRef.current++;
            draw.current.add(temp);
            draw.current.delete(e.features[0].id);
            setFeatures(JSON.stringify(draw.current.getAll()));
        }

        function deleteFeature(e) {
            draw.current.delete(e.features[0].id);
            setFeatures(JSON.stringify(draw.current.getAll()));
            setSelectedFeatureId(null);
        }

        function selectFeature(e) {
            if (e.features && e.features.length > 0) {
                const fid = e.features[0].id;
                setSelectedFeatureId(fid);
                const feat = draw.current.get(fid);
                setNameInput(feat?.properties?.name || '');
            } else {
                setSelectedFeatureId(null);
                setNameInput('');
            }
        }

        mapRef.current.on('draw.create', updateFeatures);
        mapRef.current.on('draw.delete', deleteFeature);
        mapRef.current.on('draw.update', updateFeatures);
        mapRef.current.on('draw.selectionchange', selectFeature);

        const timer = setTimeout(() => { mapRef.current?.resize(); }, 100);
        return () => { clearTimeout(timer); mapRef.current.remove(); };
    }, []);

    function applyName() {
        if (!selectedFeatureId) return;
        const feat = draw.current.get(selectedFeatureId);
        if (!feat) return;
        feat.properties = { ...(feat.properties || {}), name: nameInput };
        draw.current.add(feat);
        setFeatures(JSON.stringify(draw.current.getAll()));
    }

    return (
        <div className="flex flex-column" style={{ height: '100%' }}>
            {selectedFeatureId && (
                <div className="flex gap-2 align-items-center p-2" style={{ borderBottom: '1px solid #2a3a4a' }}>
                    <label className="text-sm">Area name:</label>
                    <InputText
                        value={nameInput}
                        onChange={e => setNameInput(e.target.value)}
                        placeholder="e.g. AreaB"
                        className="p-inputtext-sm"
                        style={{ width: 160 }}
                        onKeyDown={e => { if (e.key === 'Enter') applyName(); }}
                    />
                    <Button label="Set" size="small" onClick={applyName} />
                </div>
            )}
            <div id="map-container" ref={mapContainerRef} style={{ flex: 1 }} />
        </div>
    );
}

export default MapDraw;
```

- [ ] **Step 2: Verify naming works**

Run the dev server (`npm run dev` in `gcs/react/prime`). Navigate to Plan → Map tab. Draw a polygon. A text input labelled "Area name:" should appear. Type a name and press Enter or click Set. Draw a second polygon. Verify both can have independent names.

- [ ] **Step 3: Commit**

```bash
git add gcs/react/prime/src/MapDraw.jsx
git commit -m "feat: add per-feature naming to MapDraw"
```

---

## Task 6: `TaskNode` component

A custom React Flow node that shows the task type icon, name, instance ID, and up to 2 key params inline. Clicking a node opens editing: expand in place for ≤ 3 schema fields, or opens the `TaskNodePanel` (Task 7) for more.

**Files:**
- Create: `gcs/react/prime/src/TaskNode.jsx`

- [ ] **Step 1: Create `TaskNode.jsx`**

Create `gcs/react/prime/src/TaskNode.jsx`:

```jsx
import { useState, useCallback } from 'react';
import { Handle, Position } from '@xyflow/react';
import { InputText } from 'primereact/inputtext';
import { InputNumber } from 'primereact/inputnumber';
import { Dropdown } from 'primereact/dropdown';

// Maps type_name → icon character
const TYPE_ICONS = {
    TakeOff: '🛫', Land: '🛬', ReturnToHome: '🏠',
    Patrol: '🗺', Track: '🎯', Wait: '⏱',
    Hold: '✋', ElevateToAltitude: '⬆', PrePatrolSequence: '🔄',
    SetGimbalPose: '📷', SetGlobalPosition: '📍', SetRelativePosition: '↗',
    SetHeading: '🧭', SetVelocity: '💨', PrecisionLand: '🎯',
    AvoidTask: '🚧',
};

function FieldInput({ field, value, onChange, namedAreas }) {
    if (field.type === 'boolean') {
        return (
            <Dropdown
                value={value ?? field.default ?? false}
                options={[{ label: 'true', value: true }, { label: 'false', value: false }]}
                onChange={e => onChange(e.value)}
                className="p-inputtext-sm w-full"
            />
        );
    }
    if (field.type === 'number' || field.type === 'integer') {
        return (
            <InputNumber
                value={value ?? field.default ?? 0}
                onValueChange={e => onChange(e.value)}
                className="p-inputtext-sm w-full"
                inputStyle={{ width: '100%' }}
                useGrouping={false}
            />
        );
    }
    if (field.object_type === 'Waypoints') {
        const options = namedAreas.map(a => ({ label: a, value: a }));
        return (
            <Dropdown
                value={value?.area ?? null}
                options={options.length ? options : [{ label: '(draw area on Map tab)', value: null }]}
                onChange={e => onChange({ ...(value || {}), area: e.value })}
                className="p-inputtext-sm w-full"
                placeholder="Select area"
            />
        );
    }
    return (
        <InputText
            value={value ?? field.default ?? ''}
            onChange={e => onChange(e.target.value)}
            className="p-inputtext-sm w-full"
        />
    );
}

function TaskNode({ data, selected }) {
    const { type_name, instance_id, params, isStart, schema, namedAreas, onUpdate, onOpenPanel } = data;
    const [expanded, setExpanded] = useState(false);

    const icon = TYPE_ICONS[type_name] || '⚙';
    const fields = schema?.fields ?? [];
    const usePanel = fields.length > 3;

    const handleClick = useCallback(() => {
        if (usePanel) {
            onOpenPanel();
        } else {
            setExpanded(e => !e);
        }
    }, [usePanel, onOpenPanel]);

    function updateParam(fieldName, val) {
        onUpdate({ ...params, [fieldName]: val });
    }

    // Show first 2 non-default params as summary
    const summaryFields = fields.filter(f => f.required || params[f.name] !== undefined).slice(0, 2);

    return (
        <div
            onClick={handleClick}
            style={{
                background: '#1e3040',
                border: `2px solid ${isStart ? '#e88080' : '#4a7a9b'}`,
                borderRadius: 8,
                padding: '8px 12px',
                minWidth: 120,
                cursor: 'pointer',
                userSelect: 'none',
            }}
        >
            <Handle type="target" position={Position.Top} />
            <Handle type="source" position={Position.Bottom} />

            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: summaryFields.length ? 6 : 0 }}>
                <span style={{ fontSize: 16 }}>{icon}</span>
                <span style={{ fontWeight: 'bold', color: isStart ? '#e88080' : '#fff', fontSize: 12 }}>
                    {type_name}
                </span>
                {isStart && (
                    <span style={{ fontSize: 8, background: '#e88080', color: '#000', padding: '1px 4px', borderRadius: 3, marginLeft: 'auto' }}>
                        START
                    </span>
                )}
            </div>

            {/* Instance ID */}
            <div style={{ fontSize: 9, color: '#7ecfff', marginBottom: 4 }}>{instance_id}</div>

            {/* Collapsed summary */}
            {!expanded && summaryFields.map(f => (
                <div key={f.name} style={{ fontSize: 9, background: '#0d1820', padding: '2px 5px', borderRadius: 3, marginBottom: 2, color: '#aaa' }}>
                    {f.name}: {JSON.stringify(params[f.name] ?? f.default ?? '…')}
                </div>
            ))}

            {/* Expanded inline editing (≤3 fields only) */}
            {expanded && !usePanel && (
                <div style={{ marginTop: 6 }} onClick={e => e.stopPropagation()}>
                    {fields.map(f => (
                        <div key={f.name} style={{ marginBottom: 4 }}>
                            <label style={{ fontSize: 9, color: '#aaa', display: 'block' }}>{f.name}</label>
                            <FieldInput
                                field={f}
                                value={params[f.name]}
                                onChange={val => updateParam(f.name, val)}
                                namedAreas={namedAreas}
                            />
                        </div>
                    ))}
                    {/* Instance ID edit */}
                    <div style={{ marginTop: 4 }}>
                        <label style={{ fontSize: 9, color: '#aaa', display: 'block' }}>instance id</label>
                        <InputText
                            value={instance_id}
                            onChange={e => data.onUpdateId(e.target.value)}
                            className="p-inputtext-sm w-full"
                        />
                    </div>
                </div>
            )}
        </div>
    );
}

export default TaskNode;
```

- [ ] **Step 2: Commit**

```bash
git add gcs/react/prime/src/TaskNode.jsx
git commit -m "feat: add TaskNode custom React Flow node"
```

---

## Task 7: `TaskNodePanel` — slide-in panel for parameter-heavy nodes

A `Sidebar` (PrimeReact) that slides in from the right when a node with >3 fields is clicked. Contains the full param form plus instance-ID editing.

**Files:**
- Create: `gcs/react/prime/src/TaskNodePanel.jsx`

- [ ] **Step 1: Create `TaskNodePanel.jsx`**

Create `gcs/react/prime/src/TaskNodePanel.jsx`:

```jsx
import { Sidebar } from 'primereact/sidebar';
import { InputText } from 'primereact/inputtext';
import { InputNumber } from 'primereact/inputnumber';
import { Dropdown } from 'primereact/dropdown';
import { Button } from 'primereact/button';

function FieldInput({ field, value, onChange, namedAreas }) {
    if (field.type === 'boolean') {
        return (
            <Dropdown
                value={value ?? field.default ?? false}
                options={[{ label: 'true', value: true }, { label: 'false', value: false }]}
                onChange={e => onChange(e.value)}
                className="w-full"
            />
        );
    }
    if (field.type === 'number' || field.type === 'integer') {
        return (
            <InputNumber
                value={value ?? field.default ?? 0}
                onValueChange={e => onChange(e.value)}
                className="w-full"
                useGrouping={false}
            />
        );
    }
    if (field.object_type === 'Waypoints') {
        const options = namedAreas.map(a => ({ label: a, value: a }));
        return (
            <Dropdown
                value={value?.area ?? null}
                options={options.length ? options : [{ label: '(draw area on Map tab)', value: null }]}
                onChange={e => onChange({ ...(value || {}), area: e.value })}
                className="w-full"
                placeholder="Select area"
            />
        );
    }
    return (
        <InputText
            value={value ?? field.default ?? ''}
            onChange={e => onChange(e.target.value)}
            className="w-full"
        />
    );
}

function TaskNodePanel({ visible, onHide, node, schema, namedAreas, onUpdate, onUpdateId }) {
    if (!node) return null;
    const { type_name, instance_id, params } = node.data;
    const fields = schema?.fields ?? [];

    function updateParam(fieldName, val) {
        onUpdate(node.id, { ...params, [fieldName]: val });
    }

    return (
        <Sidebar
            visible={visible}
            position="right"
            onHide={onHide}
            style={{ width: 320 }}
            header={<span style={{ fontWeight: 'bold' }}>{type_name}</span>}
        >
            <div className="flex flex-column gap-3 p-2">
                <div>
                    <label className="text-sm text-color-secondary block mb-1">Instance ID</label>
                    <InputText
                        value={instance_id}
                        onChange={e => onUpdateId(node.id, e.target.value)}
                        className="w-full"
                    />
                </div>
                {fields.map(f => (
                    <div key={f.name}>
                        <label className="text-sm text-color-secondary block mb-1">
                            {f.name}
                            {f.required && <span style={{ color: '#e88' }}> *</span>}
                            {f.description && (
                                <span style={{ fontSize: 10, color: '#666', marginLeft: 6 }}>{f.description}</span>
                            )}
                        </label>
                        <FieldInput
                            field={f}
                            value={params[f.name]}
                            onChange={val => updateParam(f.name, val)}
                            namedAreas={namedAreas}
                        />
                    </div>
                ))}
            </div>
        </Sidebar>
    );
}

export default TaskNodePanel;
```

- [ ] **Step 2: Commit**

```bash
git add gcs/react/prime/src/TaskNodePanel.jsx
git commit -m "feat: add TaskNodePanel slide-in for parameter-heavy nodes"
```

---

## Task 8: `FsmPalette` — action palette and event reference

Fetches `/api/schema` and renders a left sidebar with draggable action chips and a non-draggable event reference list.

**Files:**
- Create: `gcs/react/prime/src/FsmPalette.jsx`

- [ ] **Step 1: Create `FsmPalette.jsx`**

Create `gcs/react/prime/src/FsmPalette.jsx`:

```jsx
import { useEffect, useState } from 'react';
import { getApiUrl } from './App.jsx';

const TYPE_ICONS = {
    TakeOff: '🛫', Land: '🛬', ReturnToHome: '🏠',
    Patrol: '🗺', Track: '🎯', Wait: '⏱',
    Hold: '✋', ElevateToAltitude: '⬆', PrePatrolSequence: '🔄',
    SetGimbalPose: '📷', SetGlobalPosition: '📍', SetRelativePosition: '↗',
    SetHeading: '🧭', SetVelocity: '💨', PrecisionLand: '🎯',
    AvoidTask: '🚧',
};

function FsmPalette({ onSchemaLoaded }) {
    const [schema, setSchema] = useState({ actions: {}, events: {} });
    const [actionsOpen, setActionsOpen] = useState(true);
    const [eventsOpen, setEventsOpen] = useState(true);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetch(getApiUrl('/api/schema'))
            .then(r => r.json())
            .then(data => {
                setSchema(data);
                onSchemaLoaded(data);
                setLoading(false);
            })
            .catch(e => { setError(e.message); setLoading(false); });
    }, []);

    function onDragStart(event, typeName) {
        event.dataTransfer.setData('application/reactflow/typeName', typeName);
        event.dataTransfer.effectAllowed = 'move';
    }

    if (loading) return <div className="p-2 text-sm text-color-secondary">Loading schema…</div>;
    if (error) return <div className="p-2 text-sm" style={{ color: '#e88' }}>Schema error: {error}</div>;

    return (
        <div style={{ width: 180, background: '#1a2530', height: '100%', overflowY: 'auto', borderRight: '1px solid #2a3a4a' }}>
            {/* Actions section */}
            <div
                className="flex align-items-center gap-2 p-2"
                style={{ cursor: 'pointer', borderBottom: '1px solid #2a3a4a', userSelect: 'none' }}
                onClick={() => setActionsOpen(o => !o)}
            >
                <i className={`pi pi-${actionsOpen ? 'chevron-down' : 'chevron-right'}`} style={{ fontSize: 10 }} />
                <span style={{ fontSize: 11, color: '#7ecfff', textTransform: 'uppercase', letterSpacing: 1 }}>Actions</span>
            </div>
            {actionsOpen && Object.keys(schema.actions).map(typeName => (
                <div
                    key={typeName}
                    draggable
                    onDragStart={e => onDragStart(e, typeName)}
                    title={schema.actions[typeName].description}
                    style={{
                        display: 'flex', alignItems: 'center', gap: 6,
                        padding: '5px 10px', cursor: 'grab', fontSize: 11,
                        borderBottom: '1px solid #1e2a38',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = '#1e3040'}
                    onMouseLeave={e => e.currentTarget.style.background = ''}
                >
                    <span>{TYPE_ICONS[typeName] || '⚙'}</span>
                    <span style={{ color: '#fff' }}>{typeName}</span>
                </div>
            ))}

            {/* Events section (reference only) */}
            <div
                className="flex align-items-center gap-2 p-2"
                style={{ cursor: 'pointer', borderBottom: '1px solid #2a3a4a', userSelect: 'none', marginTop: 8 }}
                onClick={() => setEventsOpen(o => !o)}
            >
                <i className={`pi pi-${eventsOpen ? 'chevron-down' : 'chevron-right'}`} style={{ fontSize: 10 }} />
                <span style={{ fontSize: 11, color: '#c47aff', textTransform: 'uppercase', letterSpacing: 1 }}>Events</span>
            </div>
            {eventsOpen && Object.keys(schema.events).map(typeName => (
                <div
                    key={typeName}
                    title={schema.events[typeName].description}
                    style={{
                        padding: '4px 10px', fontSize: 11,
                        borderBottom: '1px solid #1e2a38', color: '#c47aff',
                    }}
                >
                    {typeName}
                </div>
            ))}
        </div>
    );
}

export default FsmPalette;
```

- [ ] **Step 2: Commit**

```bash
git add gcs/react/prime/src/FsmPalette.jsx
git commit -m "feat: add FsmPalette that fetches schema and renders draggable actions"
```

---

## Task 9: `ConnectModal` — edge event labelling

A PrimeReact `Dialog` that fires when a new edge is drawn. Shows existing named events as selectable pills, always includes `done`, and has a form to define a new event inline.

**Files:**
- Create: `gcs/react/prime/src/ConnectModal.jsx`

- [ ] **Step 1: Create `ConnectModal.jsx`**

Create `gcs/react/prime/src/ConnectModal.jsx`:

```jsx
import { useState } from 'react';
import { Dialog } from 'primereact/dialog';
import { Button } from 'primereact/button';
import { InputText } from 'primereact/inputtext';
import { InputNumber } from 'primereact/inputnumber';
import { Dropdown } from 'primereact/dropdown';

function NewEventForm({ schema, onAdd }) {
    const eventTypes = Object.keys(schema.events || {});
    const [typeName, setTypeName] = useState(eventTypes[0] ?? '');
    const [instanceId, setInstanceId] = useState('');
    const [params, setParams] = useState({});

    const fields = typeName ? (schema.events[typeName]?.fields ?? []) : [];

    function updateParam(name, val) {
        setParams(p => ({ ...p, [name]: val }));
    }

    function handleAdd() {
        if (!typeName || !instanceId.trim()) return;
        onAdd({ instance_id: instanceId.trim(), type_name: typeName, params });
    }

    return (
        <div style={{ border: '1px solid #2a3a4a', borderRadius: 6, padding: 10, marginTop: 8 }}>
            <p style={{ fontSize: 11, color: '#7ecfff', marginBottom: 8 }}>Define new event</p>
            <div className="flex gap-2 mb-2">
                <Dropdown
                    value={typeName}
                    options={eventTypes.map(t => ({ label: t, value: t }))}
                    onChange={e => { setTypeName(e.value); setParams({}); }}
                    placeholder="Event type"
                    style={{ flex: 1 }}
                    className="p-inputtext-sm"
                />
                <InputText
                    value={instanceId}
                    onChange={e => setInstanceId(e.target.value)}
                    placeholder="instance_id"
                    className="p-inputtext-sm"
                    style={{ flex: 1 }}
                />
            </div>
            {fields.map(f => (
                <div key={f.name} className="mb-2">
                    <label style={{ fontSize: 9, color: '#aaa', display: 'block' }}>{f.name}</label>
                    {(f.type === 'number' || f.type === 'integer') ? (
                        <InputNumber
                            value={params[f.name] ?? f.default ?? 0}
                            onValueChange={e => updateParam(f.name, e.value)}
                            className="p-inputtext-sm w-full"
                            useGrouping={false}
                        />
                    ) : (
                        <InputText
                            value={params[f.name] ?? f.default ?? ''}
                            onChange={e => updateParam(f.name, e.target.value)}
                            className="p-inputtext-sm w-full"
                        />
                    )}
                </div>
            ))}
            <Button label="Add event" size="small" onClick={handleAdd} disabled={!typeName || !instanceId.trim()} />
        </div>
    );
}

function ConnectModal({ visible, onHide, connection, eventInstances, schema, onConfirm, onAddEvent }) {
    const [showNewForm, setShowNewForm] = useState(false);

    if (!connection) return null;
    const isSelfLoop = connection.source === connection.target;

    function handlePick(eventId) {
        onConfirm(connection, eventId);
        onHide();
    }

    function handleAddEvent(ev) {
        onAddEvent(ev);
        setShowNewForm(false);
        onConfirm(connection, ev.instance_id);
        onHide();
    }

    return (
        <Dialog
            header={
                <span style={{ fontSize: 13 }}>
                    Transition: {connection.source} → {isSelfLoop ? connection.source : connection.target}
                    {isSelfLoop && <span style={{ color: '#e8c87a', marginLeft: 8, fontSize: 10 }}>(self-loop)</span>}
                </span>
            }
            visible={visible}
            onHide={() => { setShowNewForm(false); onHide(); }}
            style={{ width: 360 }}
        >
            <p style={{ fontSize: 11, color: '#aaa', marginBottom: 8 }}>Trigger event:</p>

            {/* done — always shown */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
                <Button
                    label="done"
                    size="small"
                    severity="success"
                    outlined
                    onClick={() => handlePick('done')}
                />
                {eventInstances.map(ev => (
                    <Button
                        key={ev.instance_id}
                        label={ev.instance_id}
                        size="small"
                        severity="secondary"
                        outlined
                        onClick={() => handlePick(ev.instance_id)}
                    />
                ))}
            </div>

            <Button
                label={showNewForm ? '— cancel' : '+ Define new event…'}
                size="small"
                text
                onClick={() => setShowNewForm(f => !f)}
            />

            {showNewForm && (
                <NewEventForm schema={schema} onAdd={handleAddEvent} />
            )}
        </Dialog>
    );
}

export default ConnectModal;
```

- [ ] **Step 2: Commit**

```bash
git add gcs/react/prime/src/ConnectModal.jsx
git commit -m "feat: add ConnectModal for labelling FSM transitions"
```

---

## Task 10: Wire FSM Builder canvas — drag-drop, context menu, start state

Connect all components into the FSM Builder tab of `PlanPage`. Implements drag-from-palette node creation, `onConnect` → `ConnectModal`, right-click context menu (Set as Start / Delete), and the status bar.

**Files:**
- Modify: `gcs/react/prime/src/PlanPage.jsx`

- [ ] **Step 1: Replace PlanPage with fully wired version**

Replace `gcs/react/prime/src/PlanPage.jsx` entirely:

```jsx
import { useState, useCallback, useRef, useEffect } from 'react';
import { TabView, TabPanel } from 'primereact/tabview';
import { Button } from 'primereact/button';
import { Toast } from 'primereact/toast';
import { InputTextarea } from 'primereact/inputtextarea';
import {
    ReactFlow, Background, Controls, MiniMap,
    applyNodeChanges, applyEdgeChanges, addEdge,
    useReactFlow, ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import tokml from 'tokml';
import MapDraw from './MapDraw.jsx';
import TaskNode from './TaskNode.jsx';
import TaskNodePanel from './TaskNodePanel.jsx';
import FsmPalette from './FsmPalette.jsx';
import ConnectModal from './ConnectModal.jsx';
import { getApiUrl } from './App.jsx';

const nodeTypes = { taskNode: TaskNode };

let _nodeIdCounter = 1;
function nextNodeId() { return `node-${_nodeIdCounter++}`; }

// Extract named areas from GeoJSON features string
function getNamedAreas(featuresStr) {
    try {
        const fc = typeof featuresStr === 'string' ? JSON.parse(featuresStr) : featuresStr;
        return (fc.features || [])
            .map(f => f.properties?.name)
            .filter(Boolean);
    } catch { return []; }
}

function FsmCanvas({ nodes, edges, setNodes, setEdges, eventInstances, setEventInstances,
                     startNodeId, setStartNodeId, schema, features, panelNode, setPanelNode,
                     toast }) {
    const { screenToFlowPosition } = useReactFlow();
    const [connectModal, setConnectModal] = useState({ visible: false, connection: null });
    const [contextMenu, setContextMenu] = useState(null);
    const namedAreas = getNamedAreas(features);

    const onNodesChange = useCallback((changes) => setNodes(ns => applyNodeChanges(changes, ns)), []);
    const onEdgesChange = useCallback((changes) => setEdges(es => applyEdgeChanges(changes, es)), []);

    // Called when a connection is drawn between two handles (including self-loops)
    const onConnect = useCallback((connection) => {
        setConnectModal({ visible: true, connection });
    }, []);

    function confirmConnect(connection, eventId) {
        setEdges(es => addEdge({
            ...connection,
            data: { eventId },
            label: eventId,
            animated: eventId !== 'done',
            style: { stroke: eventId === 'done' ? '#a3e8a0' : '#c47aff' },
            labelStyle: { fill: eventId === 'done' ? '#a3e8a0' : '#c47aff', fontSize: 10 },
        }, es));
    }

    // Drag from palette onto canvas
    const onDragOver = useCallback((event) => {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
    }, []);

    const onDrop = useCallback((event) => {
        event.preventDefault();
        const typeName = event.dataTransfer.getData('application/reactflow/typeName');
        if (!typeName) return;

        const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
        const id = nextNodeId();
        const isFirst = nodes.length === 0;

        // Build defaults from schema
        const fields = schema.actions[typeName]?.fields ?? [];
        const defaultParams = Object.fromEntries(
            fields.filter(f => 'default' in f).map(f => [f.name, f.default])
        );

        const instanceId = typeName.replace(/([A-Z])/g, '_$1').toLowerCase().replace(/^_/, '') + '_1';

        const newNode = {
            id,
            type: 'taskNode',
            position,
            data: {
                type_name: typeName,
                instance_id: instanceId,
                params: defaultParams,
                isStart: isFirst,
                schema: schema.actions[typeName],
                namedAreas,
                onUpdate: (params) => setNodes(ns => ns.map(n => n.id === id ? { ...n, data: { ...n.data, params } } : n)),
                onUpdateId: (newId) => setNodes(ns => ns.map(n => n.id === id ? { ...n, data: { ...n.data, instance_id: newId } } : n)),
                onOpenPanel: () => setPanelNode(newNode),
            },
        };

        setNodes(ns => [...ns, newNode]);
        if (isFirst) setStartNodeId(id);
    }, [nodes, schema, namedAreas, screenToFlowPosition]);

    // Right-click context menu on a node
    const onNodeContextMenu = useCallback((event, node) => {
        event.preventDefault();
        setContextMenu({ x: event.clientX, y: event.clientY, nodeId: node.id });
    }, []);

    function setAsStart(nodeId) {
        setStartNodeId(nodeId);
        setNodes(ns => ns.map(n => ({ ...n, data: { ...n.data, isStart: n.id === nodeId } })));
        setContextMenu(null);
    }

    function deleteNode(nodeId) {
        setNodes(ns => ns.filter(n => n.id !== nodeId));
        setEdges(es => es.filter(e => e.source !== nodeId && e.target !== nodeId));
        if (startNodeId === nodeId) setStartNodeId(null);
        setContextMenu(null);
    }

    // Sync namedAreas into all node data when features change
    useEffect(() => {
        setNodes(ns => ns.map(n => ({ ...n, data: { ...n.data, namedAreas } })));
    }, [features]);

    return (
        <div style={{ flex: 1, position: 'relative' }} onClick={() => setContextMenu(null)}>
            <ReactFlow
                colorMode="dark"
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                onDragOver={onDragOver}
                onDrop={onDrop}
                onNodeContextMenu={onNodeContextMenu}
                fitView
            >
                <Controls />
                <MiniMap />
                <Background variant="dots" gap={12} size={1} />
            </ReactFlow>

            {/* Context menu */}
            {contextMenu && (
                <div
                    style={{
                        position: 'fixed', left: contextMenu.x, top: contextMenu.y,
                        background: '#1e2a38', border: '1px solid #4a7a9b', borderRadius: 6,
                        zIndex: 1000, minWidth: 160, boxShadow: '0 4px 12px #00000088',
                    }}
                    onClick={e => e.stopPropagation()}
                >
                    <div
                        style={{ padding: '8px 12px', cursor: 'pointer', fontSize: 12 }}
                        onMouseEnter={e => e.currentTarget.style.background = '#2a3a50'}
                        onMouseLeave={e => e.currentTarget.style.background = ''}
                        onClick={() => setAsStart(contextMenu.nodeId)}
                    >
                        ▶ Set as Start State
                    </div>
                    <div
                        style={{ padding: '8px 12px', cursor: 'pointer', fontSize: 12, color: '#e88080' }}
                        onMouseEnter={e => e.currentTarget.style.background = '#2a3a50'}
                        onMouseLeave={e => e.currentTarget.style.background = ''}
                        onClick={() => deleteNode(contextMenu.nodeId)}
                    >
                        🗑 Delete
                    </div>
                </div>
            )}

            <ConnectModal
                visible={connectModal.visible}
                onHide={() => setConnectModal({ visible: false, connection: null })}
                connection={connectModal.connection}
                eventInstances={eventInstances}
                schema={schema}
                onConfirm={confirmConnect}
                onAddEvent={(ev) => setEventInstances(evs => [...evs, ev])}
            />
        </div>
    );
}

function PlanPage({ vehicles, squadList }) {
    const [nodes, setNodes] = useState([]);
    const [edges, setEdges] = useState([]);
    const [eventInstances, setEventInstances] = useState([]);
    const [startNodeId, setStartNodeId] = useState(null);
    const [schema, setSchema] = useState({ actions: {}, events: {} });
    const [compiledMission, setCompiledMission] = useState(null);
    const [features, setFeatures] = useState(JSON.stringify({ type: 'FeatureCollection', features: [] }));
    const [panelNode, setPanelNode] = useState(null);
    const [compiling, setCompiling] = useState(false);
    const [deploying, setDeploying] = useState(false);
    const toast = useRef(null);

    const startNode = nodes.find(n => n.id === startNodeId);

    async function handleCompile() {
        if (!startNodeId) {
            toast.current.show({ severity: 'warn', summary: 'No start state', detail: 'Right-click a node and set it as the start state.' });
            return;
        }
        setCompiling(true);
        try {
            const body = {
                nodes: nodes.map(n => ({
                    instance_id: n.data.instance_id,
                    type_name: n.data.type_name,
                    params: n.data.params,
                })),
                events: eventInstances,
                edges: edges.map(e => ({
                    source: nodes.find(n => n.id === e.source)?.data.instance_id,
                    event_id: e.data?.eventId ?? 'done',
                    target: nodes.find(n => n.id === e.target)?.data.instance_id,
                })),
                start_id: startNode?.data.instance_id,
            };
            const resp = await fetch(getApiUrl('/api/compile'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const result = await resp.json();
            if (result.errors) {
                toast.current.show({ severity: 'error', summary: 'Compile error', detail: result.errors[0]?.message });
                // Highlight error nodes
                const errorIds = new Set(result.errors.map(e => e.node_id));
                setNodes(ns => ns.map(n => ({
                    ...n,
                    data: { ...n.data, _hasError: errorIds.has(n.data.instance_id) },
                })));
            } else {
                setCompiledMission(result.mission);
                toast.current.show({ severity: 'success', summary: 'Compiled', detail: 'mission.json ready.' });
            }
        } catch (e) {
            toast.current.show({ severity: 'error', summary: 'Compile failed', detail: e.message });
        } finally {
            setCompiling(false);
        }
    }

    function handleDownload() {
        if (!compiledMission) return;
        const blob = new Blob([JSON.stringify(compiledMission, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'mission.json';
        a.click();
        URL.revokeObjectURL(url);
    }

    async function handleDeploy() {
        if (!compiledMission) {
            toast.current.show({ severity: 'warn', summary: 'Not compiled', detail: 'Compile the mission first.' });
            return;
        }
        if (!squadList || squadList.length === 0) {
            toast.current.show({ severity: 'warn', summary: 'No vehicles', detail: 'Select at least one vehicle in the Control panel first.' });
            return;
        }
        setDeploying(true);
        try {
            const featObj = typeof features === 'string' ? JSON.parse(features) : features;
            const kmlString = tokml(featObj);
            const kml = btoa(kmlString);
            const dsl = btoa(JSON.stringify(compiledMission));
            const resp = await fetch(getApiUrl('/api/upload'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ kml, dsl, vehicles: squadList }),
            });
            if (!resp.ok) {
                const err = await resp.json();
                toast.current.show({ severity: 'error', summary: 'Deploy failed', detail: err.detail });
            } else {
                toast.current.show({ severity: 'success', summary: 'Deployed', detail: `Mission sent to ${squadList.join(', ')}.` });
            }
        } catch (e) {
            toast.current.show({ severity: 'error', summary: 'Deploy failed', detail: e.message });
        } finally {
            setDeploying(false);
        }
    }

    function updateNodeParams(nodeId, params) {
        setNodes(ns => ns.map(n => n.id === nodeId ? { ...n, data: { ...n.data, params } } : n));
    }

    function updateNodeId(nodeId, newId) {
        setNodes(ns => ns.map(n => n.id === nodeId ? { ...n, data: { ...n.data, instance_id: newId } } : n));
    }

    return (
        <>
            <Toast ref={toast} />
            <TabView style={{ height: 'calc(100vh - 110px)' }}>
                <TabPanel header="FSM Builder" leftIcon="pi pi-share-alt mr-2">
                    <div className="flex flex-column" style={{ height: 'calc(100vh - 180px)' }}>
                        <div className="flex flex-1" style={{ overflow: 'hidden' }}>
                            <FsmPalette onSchemaLoaded={setSchema} />
                            <ReactFlowProvider>
                                <FsmCanvas
                                    nodes={nodes} edges={edges}
                                    setNodes={setNodes} setEdges={setEdges}
                                    eventInstances={eventInstances} setEventInstances={setEventInstances}
                                    startNodeId={startNodeId} setStartNodeId={setStartNodeId}
                                    schema={schema} features={features}
                                    panelNode={panelNode} setPanelNode={setPanelNode}
                                    toast={toast}
                                />
                            </ReactFlowProvider>
                        </div>

                        {/* Toolbar */}
                        <div className="flex gap-2 align-items-center p-2" style={{ borderTop: '1px solid #2a3a4a', flexShrink: 0 }}>
                            <Button
                                label="Compile"
                                icon="pi pi-cog"
                                size="small"
                                loading={compiling}
                                onClick={handleCompile}
                            />
                            <Button
                                label="Download .json"
                                icon="pi pi-download"
                                size="small"
                                outlined
                                disabled={!compiledMission}
                                onClick={handleDownload}
                            />
                            <Button
                                label={`Deploy → ${squadList?.length ? squadList.join(', ') : 'no vehicles'}`}
                                icon="pi pi-send"
                                size="small"
                                severity="success"
                                disabled={!compiledMission}
                                loading={deploying}
                                onClick={handleDeploy}
                            />
                            <span className="text-sm text-color-secondary ml-auto">
                                {nodes.length} actions · {eventInstances.length} events
                                {startNode
                                    ? ` · start: ${startNode.data.instance_id}`
                                    : ' · ⚠ no start set'}
                            </span>
                        </div>
                    </div>

                    {/* Slide-in panel for parameter-heavy nodes */}
                    <TaskNodePanel
                        visible={!!panelNode}
                        onHide={() => setPanelNode(null)}
                        node={panelNode}
                        schema={panelNode ? schema.actions[panelNode.data.type_name] : null}
                        namedAreas={getNamedAreas(features)}
                        onUpdate={updateNodeParams}
                        onUpdateId={updateNodeId}
                    />
                </TabPanel>

                <TabPanel header="Map" leftIcon="pi pi-map mr-2">
                    <div style={{ height: 'calc(100vh - 180px)' }}>
                        <MapDraw features={features} setFeatures={setFeatures} />
                    </div>
                </TabPanel>

                <TabPanel header="JSON Output" leftIcon="pi pi-code mr-2">
                    <InputTextarea
                        style={{ width: '100%', height: 'calc(100vh - 200px)', fontFamily: 'monospace', fontSize: 12 }}
                        readOnly
                        value={compiledMission ? JSON.stringify(compiledMission, null, 2) : '// compile a mission to see output'}
                    />
                </TabPanel>
            </TabView>
        </>
    );
}

export default PlanPage;
```

- [ ] **Step 2: Verify the FSM Builder works end-to-end**

```bash
cd gcs/react/prime
npm run dev
```

Open the Plan page. In the FSM Builder tab:
1. Drag "TakeOff" from the palette → a node appears on the canvas with a START badge
2. Drag "Patrol" → a second node appears
3. Drag from TakeOff's bottom handle to Patrol's top handle → ConnectModal appears
4. Click "done" → the edge is created labelled "done"
5. Drag from Patrol to itself (self-loop) → ConnectModal appears; click "done" → self-loop edge
6. Right-click TakeOff → context menu shows; "Set as Start State" reassigns the badge
7. Click Compile → success toast; JSON Output tab shows the compiled mission
8. Click Download → browser downloads `mission.json`
9. With vehicles selected in the Control tab and the squad list set, Deploy sends to vehicles

- [ ] **Step 3: Build and commit**

```bash
cd gcs/react/prime && npm run build
git add gcs/react/prime/src/PlanPage.jsx gcs/react/prime/src/App.jsx
git commit -m "feat: wire FSM Builder canvas with drag-drop, compile, and deploy"
```

---

## Self-review checklist (completed inline before committing plan)

**Spec coverage:**
- [x] Tabbed layout (FSM Builder / Map / JSON Output) — Task 4, 10
- [x] Palette: draggable actions, event reference — Task 8
- [x] TaskNode: icon + name + key params + START badge — Task 6
- [x] Expand in place ≤3 fields — Task 6
- [x] Slide-in panel >3 fields — Task 7
- [x] Waypoints fields → named-area dropdown — Tasks 6, 7
- [x] Self-referential edges allowed — Task 10 (`onConnect` has no source==target guard)
- [x] First node dropped = start state — Task 10
- [x] Right-click → Set as Start / Delete — Task 10
- [x] ConnectModal on connect — Tasks 9, 10
- [x] `done` always available; named events defined inline — Task 9
- [x] MapDraw feature naming — Task 5
- [x] Named features available in node config — Tasks 6, 7 (`namedAreas` prop)
- [x] Compile → POST /api/compile — Tasks 3, 10
- [x] Download mission.json — Task 10
- [x] Deploy → tokml + POST /api/upload + squadList — Task 10
- [x] `/api/schema` backend endpoint + tests — Task 2
- [x] `/api/compile` backend endpoint + tests — Task 3
- [x] Local SDK path dep (fixes missing grammar file) — Task 1

**No placeholders found.**

**Type consistency:** `CompileNode`, `CompileEvent`, `CompileEdge`, `CompileRequest` defined in Task 3 and used only there. `build_schema_response` defined in Task 2, tested in Task 2. `compile_mission` defined in Task 3, tested in Task 3. Frontend types flow correctly: `nodes[].data.instance_id` used in compile body, `edges[].data.eventId` used for transitions.
