# FSM Pre-Compile Validation Design

## Goal

Surface low-hanging-fruit errors inline on the canvas and in the status bar before the user hits Compile, without a network round-trip.

## Architecture

Validation is a pure client-side computation triggered by a debounced `useEffect` in `PlanPage`. Results flow down as node data props (`_warnings`) and drive the status bar warning count. No backend call is made — the compile endpoint handles deeper Pydantic type validation.

**New file:** `gcs/react/prime/src/validation.js`
**Modified files:** `PlanPage.jsx`, `TaskNode.jsx`

---

## Layout Change

The FSM Builder tab toolbar moves **above** the canvas (matching IDE convention: toolbar → canvas → status bar):

```
┌─────────────────────────────────────────────────────┐
│ [↩] [↪] [Load DSL] [Export DSL] [Compile] [Deploy] │  toolbar
├──────────┬──────────────────────────────────────────┤
│ Palette  │         React Flow Canvas                │  canvas
├──────────┴──────────────────────────────────────────┤
│ 3 actions · 1 event · start: p1 · ⚠ 2 warnings     │  status bar
└─────────────────────────────────────────────────────┘
```

The toolbar sits between the TabView header row and the palette+canvas row. The status bar remains at the bottom.

---

## Validation Checks

Three checks run on every debounced validation pass:

### 1. Required field not set
For each node, walk `schema.actions[type_name].fields`. For every field where `required === true`, check if `params[name]` is `undefined`, `null`, or `''`. If so, record: `"<fieldName> is required"` against that node's ID.

### 2. Duplicate instance ID
Build a frequency map of `node.data.instance_id` values. Any node whose ID appears more than once gets: `"Duplicate ID '<instance_id>'"`.

### 3. No start state
If `startNodeId` is `null` or `undefined`, set `noStart: true` in the result. This is a canvas-level issue with no specific node to highlight — surfaces in the status bar only.

---

## `validation.js`

Pure function, no React dependencies:

```js
// Returns { issues: { [reactFlowNodeId]: string[] }, noStart: boolean }
export function runValidation(nodes, schema, startNodeId) { ... }
```

- `nodes` — React Flow node array (with `data.type_name`, `data.instance_id`, `data.params`)
- `schema` — `{ actions: { [typeName]: { fields: [...] } } }`
- `startNodeId` — current start node React Flow ID or null

Returns:
- `issues` — map from React Flow node `id` to array of warning strings
- `noStart` — boolean

---

## `PlanPage.jsx` Changes

### New state
```js
const [validationIssues, setValidationIssues] = useState({});
```

### Debounced validation effect
```js
useEffect(() => {
    const timer = setTimeout(() => {
        const result = runValidation(nodes, schema, startNodeId);
        setValidationIssues(result.issues);
    }, 500);
    return () => clearTimeout(timer);
}, [nodes, startNodeId, schema]);
```

### Inject `_warnings` into node data
When passing nodes to `FsmCanvas`, map each node to include:
```js
{ ...n, data: { ...n.data, _warnings: validationIssues[n.id] ?? [] } }
```
This is computed inline (not stored in nodes state) so it doesn't pollute the undo history.

### Status bar update
Current: `{nodes.length} actions · {eventInstances.length} events · start: {id} / ⚠ no start set`

New (appended):
- If `totalWarnings > 0`: `· ⚠ {N} warning{s}` in amber (`#e8c87a`)
- `noStart` condition: text becomes `· ⚠ no start set` in amber (replaces current plain text variant)

`totalWarnings` = sum of all `validationIssues[id].length` values.

### Toolbar position
Move the toolbar `<div>` from below `FsmCanvas` to above it (between the tab content wrapper and the `flex-1` canvas row).

---

## `TaskNode.jsx` Changes

### Border color priority
```js
const borderColor = _hasError  ? '#ff4444'   // red   — compile error
                  : _warnings?.length ? '#e8c87a'  // amber — pre-compile warning
                  : isStart    ? '#a3e8a0'   // green — start state
                  :              '#4a7a9b';  // blue  — default
```

### Warning badge
When `_warnings?.length > 0`, render a small amber badge in the top-right corner of the node (same row as the START chip). Badge shows `⚠ {count}`. The `title` attribute on the badge element contains the newline-joined warning messages for native tooltip display.

```jsx
{_warnings?.length > 0 && (
    <span title={_warnings.join('\n')}
          style={{ fontSize: 8, background: '#e8c87a', color: '#000',
                   padding: '1px 4px', borderRadius: 3, marginLeft: 'auto' }}>
        ⚠ {_warnings.length}
    </span>
)}
```

The START chip and warning badge coexist in the same header row — START chip on the left of `marginLeft: auto`, warning badge on the right (or both present if a node is both the start and has warnings, with the warning badge taking `marginLeft: 4`).

---

## What Is NOT Validated Client-Side

- Param type correctness (numbers in range, valid enum values) — Pydantic handles this at compile time
- Unknown type names — these only originate from the schema, so they're always valid on the canvas
- Edge referential integrity — the canvas enforces this structurally

---

## Non-Goals

- No backend call during live validation
- No separate Issues panel or drawer
- No validation of event params (out of scope for this iteration)
