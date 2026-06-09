# FSM Mission Builder — Design Spec

**Date:** 2026-06-09
**Status:** Approved
**Branch:** python-orchestration

---

## Overview

Replace the placeholder `PlanPage` with a drag-and-drop finite state machine (FSM) editor that lets users visually compose SteelEagle missions, compile them to `mission.json` via the Python backend, and deploy directly to vehicles.

---

## Architecture

```
Frontend (React)                    Backend (FastAPI)              SDK
─────────────────────────────────   ────────────────────────────   ──────────────────
PlanPage (tabbed)
  FSM Builder tab
    ├── Palette (from /api/schema)  GET  /api/schema ────────────► registry.py
    ├── React Flow canvas                                            model_json_schema()
    └── Toolbar
          ├── Compile ─────────── POST /api/compile ──────────────► MissionIR + validator
          ├── Download .json                                         → mission.json
          └── Deploy ──────────── POST /api/upload (existing)
  Map tab
    └── MapDraw (named features)
  JSON Output tab (read-only)

tokml (npm) — GeoJSON → KML conversion, client-side, before /api/upload
```

---

## Frontend

### PlanPage restructure

`PlanPage.jsx` is reorganised around a PrimeReact `TabView` with three tabs. State that lives in `PlanPage`:

| State | Type | Description |
|---|---|---|
| `nodes` | RF node array | Action instances on the canvas |
| `edges` | RF edge array | Transition connections |
| `eventInstances` | `[{instance_id, type_name, params}]` | Named event definitions (shared across edges) |
| `startNodeId` | string \| null | ID of the start node |
| `schema` | object | Fetched from `/api/schema` on mount |
| `compiledMission` | object \| null | Last successful compile result |
| `features` | GeoJSON FeatureCollection | From MapDraw (named polygons/lines) |

### Tab 1 — FSM Builder

**Palette (left, ~180px)**
Two collapsible sections populated from `schema`:
- *Actions* — draggable chips; dropping onto the canvas creates a new `TaskNode`
- *Events* — reference list of available event types (not draggable); all event instantiation happens inside `ConnectModal` when wiring edges

**Canvas (center)**
React Flow with:
- Custom `TaskNode` component
- Self-referential edges explicitly allowed (e.g. `patrol --done--> patrol`)
- Right-click context menu on nodes: *Set as Start State*, *Delete*
- `onConnect` callback opens `ConnectModal`

**Bottom toolbar**
`[ Compile ]  [ ↓ Download mission.json ]  [ ▶ Deploy → <vehicle selector> ]`
A status line shows: `3 actions · 2 events · start: take_off` or a warning if no start node is set.

### Task Node (`TaskNode`)

Each node renders:
- Icon (type→icon map: TakeOff→🛫, Patrol→🗺, Track→🎯, RTH→🏠, Wait→⏱, etc.)
- Bold type name
- Up to 2 key params inline (first non-default fields from schema)
- Red border + **START** badge if `data.isStart === true`

**Node data shape:**
```js
{
  id: "node-1",
  type: "taskNode",
  data: {
    type_name: "Patrol",
    instance_id: "patrol",       // user-editable snake_case, used in mission.json
    params: { hover_time: 1.0, waypoints: { area: "AreaB", alt: 15.0, algo: "edge" } },
    isStart: false
  },
  position: { x, y }
}
```

**Parameter editing:**
- ≤ 3 schema fields → click expands node in place with inline inputs
- > 3 schema fields → click opens a slide-in panel on the right edge of the canvas
- `Waypoints`-type fields render a dropdown populated from named features in `features` state instead of a free-text input. If no named features exist, a hint reads "Draw a named area in the Map tab."

**Start state assignment:**
- First node dropped on the canvas is automatically set as start (`startNodeId` = its id, `data.isStart = true`)
- Right-click → *Set as Start State* reassigns start to any other node

### ConnectModal

Fires when `onConnect` is triggered (including self-connections where `source === target`).

Contents:
- **Existing named events** — pill buttons for each entry in `eventInstances`
- **`done`** — always present, reserved keyword, no params
- **Define new event** — type picker (from `schema.events`), instance ID input, param form; confirms and adds to `eventInstances`

On confirm, the edge is added with `data.eventId` set to the selected/new event's `instance_id` (or `"done"`). The edge label renders that ID.

### Tab 2 — Map

The existing `MapDraw` component, unchanged except for one addition: when a feature is drawn or selected, a small text input appears to give it a name (stored in `feature.properties.name`). The `features` GeoJSON state flows up to `PlanPage` as before.

### Tab 3 — JSON Output

Read-only `InputTextarea` showing `JSON.stringify(compiledMission, null, 2)`. Only populated after a successful compile. Useful for debugging.

---

## Backend

### `GET /api/schema`

Calls `load_all()` to ensure all `@register_action` / `@register_event` classes are imported, then iterates `_ACTIONS` and `_EVENTS` from `registry.py`. For each class, calls `cls.model_json_schema()` to extract field metadata.

**Response shape:**
```json
{
  "actions": {
    "Patrol": {
      "description": "Fly through waypoints...",
      "fields": [
        { "name": "hover_time", "type": "number", "default": 1.0, "required": false, "description": "..." },
        { "name": "waypoints",  "type": "object", "default": null, "required": true,  "description": "..." }
      ]
    }
  },
  "events": {
    "DetectionFound": { ... },
    "BatteryReached":  { ... }
  }
}
```

### `POST /api/compile`

**Request body:**
```json
{
  "nodes":  [{ "instance_id": "patrol", "type_name": "Patrol", "params": { "hover_time": 1.0, "waypoints": { "area": "AreaB", "alt": 15.0, "algo": "edge" } } }],
  "events": [{ "instance_id": "person_seen", "type_name": "DetectionFound", "params": { "target": { "class_name": "person", "score": 60.0 } } }],
  "edges":  [
    { "source": "patrol", "event_id": "person_seen", "target": "track" },
    { "source": "patrol", "event_id": "done",         "target": "patrol" }
  ],
  "start_id": "patrol"
}
```

**Logic:**
1. Validate all `type_name` values exist in the registry
2. Construct `MissionIR`:
   - `actions`: `{ instance_id: ActionIR(type_name, instance_id, params) }`
   - `events`:  `{ instance_id: EventIR(type_name, instance_id, params) }`
   - `data`: `{}` (empty for now; could be extended later for explicit data stanza)
   - `start_action_id`: `start_id`
   - `transitions`: built from edges — `{ source: { event_id: target } }` (self-loops allowed)
3. Instantiate each action/event Pydantic class with its params to trigger field validation
4. Serialize `MissionIR` to dict and return

**Success response:**
```json
{ "mission": { ...mission.json contents... } }
```

**Error response (422):**
```json
{ "errors": [{ "node_id": "patrol", "message": "waypoints.area is required" }] }
```

---

## Compile & Deploy Flow

```
1. User clicks Compile
   POST /api/compile { nodes, events, edges, start_id }
   ← { mission } or { errors }

2a. Error → toast + highlight offending nodes/edges in red

2b. Success →
    - Store mission in compiledMission state
    - Enable Download button: browser download of mission.json
    - Enable Deploy button

3. User selects vehicles (existing squadList from App.jsx)
   Clicks Deploy:
     kml = btoa(tokml(features))     // tokml npm package, client-side
     dsl = btoa(JSON.stringify(mission))
     POST /api/upload { kml, dsl, vehicles: squadList }
   ← success/error toast (existing pattern)
```

---

## Dependencies

| Package | Where | Purpose |
|---|---|---|
| `@xyflow/react` | frontend | Already installed |
| `tokml` | frontend | GeoJSON → KML (new, add to prime/package.json) |
| `fastkml` / stdlib | backend | Not needed — conversion is client-side |

---

## Out of Scope

- Editing the DSL text directly (text editor is removed from PlanPage)
- Saving/loading FSM graphs to the server (browser localStorage could be added later)
- Multi-vehicle FSMs (one mission.json per compile)
- Composite/custom action and event types beyond what the registry already exposes
