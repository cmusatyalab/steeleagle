# Light/Dark Theme Toggle Design

## Goal

Let the user switch the GCS React UI between the current dark theme and a matching light theme, via a compact switch in the top menu bar, with the choice remembered across reloads.

## Architecture

The app already links its PrimeReact theme via a single `<link id="theme-link">` tag in `index.html`. Theme switching is implemented as a runtime swap of that link's `href` between two theme CSS bundles, driven by a `theme` state value (`'dark' | 'light'`) in `App.jsx`. The choice is persisted to `localStorage` and re-applied synchronously before first paint to avoid a flash of the wrong theme.

This app currently has no precedent for persisting settings (connection mode, gamepad deadzone, etc. all reset on reload) — theme is treated as an exception because it's a one-time visual preference rather than session state, per explicit user decision during design.

**New files:** `gcs/react/prime/public/themes/lara-light-amber/` (theme CSS + fonts, copied from PrimeReact's bundled themes)
**Modified files:** `index.html`, `App.jsx`, `PlanPage.jsx`

## Theme Assets

Copy PrimeReact's bundled `lara-light-amber` theme into `public/themes/lara-light-amber/`, mirroring the existing committed `public/themes/lara-dark-amber/` directory (theme.css + `fonts/` subdirectory). Source: `node_modules/primereact/resources/themes/lara-light-amber/`. Both directories are committed to git, same as the existing dark theme.

## No-Flash-on-Load

`index.html` currently has:
```html
<link id="theme-link" rel="stylesheet" href="/themes/lara-dark-amber/theme.css">
```

Add an inline `<script>` immediately before this link tag that reads the stored preference and writes the correct `href` before the stylesheet request fires:
```html
<script>
  (function () {
    var t = localStorage.getItem('se-theme') || 'dark';
    document.write('<link id="theme-link" rel="stylesheet" href="/themes/lara-' + t + '-amber/theme.css">');
  })();
</script>
```
This replaces the static `<link>` tag — the script emits it with the correct href on first parse, before any paint, so a saved "light" preference never flashes dark.

## `App.jsx` Changes

### New state
Alongside the existing settings state (~line 61, near `useLocalVehicle`):
```js
const [theme, setTheme] = useState(() => localStorage.getItem('se-theme') || 'dark');
```

### Sync effect
```js
useEffect(() => {
    document.getElementById('theme-link').href = `/themes/lara-${theme}-amber/theme.css`;
    localStorage.setItem('se-theme', theme);
}, [theme]);
```

### UI placement
In `menuBarEnd` (~line 473), add a moon icon, `InputSwitch`, and sun icon immediately to the left of the existing gear `Button`:
```jsx
<i className="pi pi-moon" />
<InputSwitch checked={theme === 'light'} onChange={(e) => setTheme(e.value ? 'light' : 'dark')} />
<i className="pi pi-sun" />
```
`InputSwitch` is imported from `primereact/inputswitch` (new import). Off (left, moon) = dark, on (right, sun) = light.

The "Connection Mode" `SelectButton` inside the gear icon's `OverlayPanel` (`overlayContent`, ~line 446) is unchanged — the theme switch lives in the menu bar itself, not inside that popover.

## `PlanPage.jsx` (FSM Canvas) Changes

The FSM canvas on the Plan tab is a separate rendering surface from PrimeReact — `@xyflow/react`'s `<ReactFlow>` component ships its own CSS variables for edges, the minimap, the background, and controls, switched via a `colorMode` prop (`'light' | 'dark' | 'system'`). It's currently hardcoded:
```jsx
<ReactFlow colorMode="dark" ... >
```
(`PlanPage.jsx:269`). Our `theme` state values (`'dark'`/`'light'`) are exactly the values `colorMode` accepts, so no mapping is needed — only threading the value through:
- `App.jsx` passes `theme={theme}` to `<PlanPage>` (currently `<PlanPage vehicles={vehicles} squadList={squadList} />`, `App.jsx:522`).
- `PlanPage.jsx` accepts `theme` as a new prop. The actual `<ReactFlow>` element lives one level deeper, in an inner `FsmCanvas` component that `PlanPage` renders inside a `<ReactFlowProvider>` — `PlanPage` forwards `theme` as a prop to `<FsmCanvas>`, which forwards it to `colorMode={theme}`.

No new CSS is needed — `@xyflow/react/dist/style.css` (already imported in `PlanPage.jsx`) defines light-mode variables as the base defaults and overrides them under a `.react-flow.dark` class, which the `colorMode` prop toggles automatically.

## Data Flow

1. Page load: inline script in `<head>` sets the initial theme link `href` from `localStorage` (or defaults to dark) before any stylesheet loads.
2. React mounts: `theme` state is initialized from the same `localStorage` key, so it matches what's already rendered. The sync effect still runs once on mount (React's normal behavior) and reassigns the same `href` — a harmless no-op, not a visible swap.
3. User flips the switch: `setTheme` updates state → `useEffect` updates the `<link>` href (browser swaps the stylesheet) and writes the new value to `localStorage`.
4. Next reload: step 1 picks up the new value.

## Testing

Pure UI wiring with no business logic — verified manually by running the dev server: toggle the switch and confirm the stylesheet swaps, reload and confirm the choice persisted, check that the panels touched in the recent `FieldInput` fixes (numeric inputs, nested fields) still render correctly under the light theme, and check the Plan tab's FSM canvas (edges, minimap, background dots) re-themes along with everything else.

## Non-Goals

- No per-component custom light-mode styling — relying entirely on PrimeReact's bundled `lara-light-amber` theme.
- No system-preference (`prefers-color-scheme`) auto-detection.
- No change to the Connection Mode control or any other existing settings-panel content.
