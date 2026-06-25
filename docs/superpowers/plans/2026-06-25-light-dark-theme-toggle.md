# Light/Dark Theme Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a menu-bar switch that toggles the GCS React UI between PrimeReact's `lara-dark-amber` (current) and `lara-light-amber` themes, with the choice persisted across reloads.

**Architecture:** A single `<link id="theme-link">` tag already drives the active theme CSS. Theme switching is a runtime swap of that link's `href`, driven by a `theme` state value (`'dark' | 'light'`) in `App.jsx`, persisted to `localStorage`, and applied before first paint via an inline script in `index.html` to avoid a flash of the wrong theme.

**Tech Stack:** React 19, PrimeReact 10.9.7 (`InputSwitch`, bundled `lara-light-amber`/`lara-dark-amber` themes), Vite 7, vanilla `localStorage`.

## Global Constraints

- No new npm dependencies — `InputSwitch` and both theme CSS bundles already ship inside the installed `primereact` package (`node_modules/primereact`).
- Persisted localStorage key is exactly `se-theme`, values exactly `'dark'` or `'light'`.
- Theme asset folder naming is `lara-<dark|light>-amber`, matching PrimeReact's own bundled theme directory names — do not rename.
- Spec source of truth: `docs/superpowers/specs/2026-06-25-light-dark-theme-toggle-design.md`.

---

### Task 1: Add `lara-light-amber` theme assets

**Files:**
- Create: `gcs/react/prime/public/themes/lara-light-amber/theme.css`
- Create: `gcs/react/prime/public/themes/lara-light-amber/fonts/InterVariable.woff2`
- Create: `gcs/react/prime/public/themes/lara-light-amber/fonts/InterVariable-Italic.woff2`

**Interfaces:**
- Produces: a theme bundle servable at `/themes/lara-light-amber/theme.css` (static asset, served by Vite from `public/`), matching the existing `/themes/lara-dark-amber/theme.css` that's already committed. Task 2 and Task 3 reference this path by string template — no code interface, just the path contract `/themes/lara-light-amber/theme.css`.

- [ ] **Step 1: Copy the theme directory from the installed package**

Run from the repo root:
```bash
cp -r gcs/react/prime/node_modules/primereact/resources/themes/lara-light-amber gcs/react/prime/public/themes/lara-light-amber
```

- [ ] **Step 2: Verify it's an exact, unmodified copy**

```bash
diff -rq gcs/react/prime/node_modules/primereact/resources/themes/lara-light-amber gcs/react/prime/public/themes/lara-light-amber
```
Expected: no output (the two directories are byte-identical).

- [ ] **Step 3: Confirm the copied CSS references fonts with a relative path**

This is what makes the copy self-contained (no path rewriting needed):
```bash
grep -c 'url("./fonts/' gcs/react/prime/public/themes/lara-light-amber/theme.css
```
Expected: `2`

- [ ] **Step 4: Commit**

```bash
git add gcs/react/prime/public/themes/lara-light-amber
git commit -m "Add lara-light-amber theme assets for light mode toggle"
```

---

### Task 2: Apply the saved theme before first paint (`index.html`)

**Files:**
- Modify: `gcs/react/prime/index.html`

**Interfaces:**
- Consumes: theme asset paths produced by Task 1 (`/themes/lara-light-amber/theme.css`, `/themes/lara-dark-amber/theme.css`).
- Produces: a `<link id="theme-link">` element in the DOM whose `href` is correct on first paint, read from `localStorage.getItem('se-theme')`. Task 3's `useEffect` looks up this same element by `id="theme-link"`.

The current file:
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/logo.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>SteelEagle GCS</title>
    <link id="theme-link" rel="stylesheet" href="/themes/lara-dark-amber/theme.css">
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 1: Replace the static `<link>` with a theme-aware inline script**

Replace this line:
```html
    <link id="theme-link" rel="stylesheet" href="/themes/lara-dark-amber/theme.css">
```
with:
```html
    <script>
      (function () {
        var t = localStorage.getItem('se-theme') || 'dark';
        document.write('<link id="theme-link" rel="stylesheet" href="/themes/lara-' + t + '-amber/theme.css">');
      })();
    </script>
```

- [ ] **Step 2: Start the dev server**

```bash
cd gcs/react/prime && npx vite --port 5179 --strictPort > /tmp/vite-theme.log 2>&1 &
sleep 2 && cat /tmp/vite-theme.log
```
Expected: log includes `Local:   http://localhost:5179/`

- [ ] **Step 3: Launch headless Chrome with remote debugging**

```bash
google-chrome --headless=new --disable-gpu --no-sandbox --remote-debugging-port=9333 --remote-allow-origins=* about:blank > /tmp/chrome-theme.log 2>&1 &
sleep 2 && curl -s http://localhost:9333/json/version
```
Expected: JSON containing `"webSocketDebuggerUrl"`.

- [ ] **Step 4: Write the verification script**

Save as `/tmp/verify-theme-link.mjs`:
```js
const CDP = 'http://localhost:9333';

function connect(wsUrl) {
    return new Promise((resolve, reject) => {
        const ws = new WebSocket(wsUrl);
        ws.addEventListener('open', () => resolve(ws));
        ws.addEventListener('error', reject);
    });
}
function send(ws, method, params = {}) {
    const id = Math.floor(Math.random() * 1e9);
    return new Promise((resolve) => {
        const handler = (ev) => {
            const msg = JSON.parse(ev.data);
            if (msg.id === id) { ws.removeEventListener('message', handler); resolve(msg.result); }
        };
        ws.addEventListener('message', handler);
        ws.send(JSON.stringify({ id, method, params }));
    });
}
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function getHref(ws) {
    const r = await send(ws, 'Runtime.evaluate', {
        expression: `document.getElementById('theme-link').href`,
        returnByValue: true,
    });
    return r.result.value;
}

async function main() {
    const res = await fetch(`${CDP}/json/new?http://localhost:5179/`, { method: 'PUT' });
    const tab = await res.json();
    const ws = await connect(tab.webSocketDebuggerUrl);
    await send(ws, 'Page.enable');
    await send(ws, 'Runtime.enable');
    await sleep(800);

    console.log('DEFAULT (no stored pref):', await getHref(ws));

    await send(ws, 'Runtime.evaluate', { expression: `localStorage.setItem('se-theme', 'light')` });
    await send(ws, 'Page.reload', {});
    await sleep(800);
    console.log('AFTER setting se-theme=light + reload:', await getHref(ws));

    await send(ws, 'Runtime.evaluate', { expression: `localStorage.setItem('se-theme', 'dark')` });
    await send(ws, 'Page.reload', {});
    await sleep(800);
    console.log('AFTER setting se-theme=dark + reload:', await getHref(ws));

    ws.close();
    process.exit(0);
}
main().catch(e => { console.error(e); process.exit(1); });
```

- [ ] **Step 5: Run it**

```bash
node /tmp/verify-theme-link.mjs
```
Expected output:
```
DEFAULT (no stored pref): http://localhost:5179/themes/lara-dark-amber/theme.css
AFTER setting se-theme=light + reload: http://localhost:5179/themes/lara-light-amber/theme.css
AFTER setting se-theme=dark + reload: http://localhost:5179/themes/lara-dark-amber/theme.css
```

- [ ] **Step 6: Stop processes and clean up**

```bash
pkill -f "remote-debugging-port=9333"
pkill -f "vite --port 5179"
rm -f /tmp/verify-theme-link.mjs /tmp/vite-theme.log /tmp/chrome-theme.log
```

- [ ] **Step 7: Commit**

```bash
git add gcs/react/prime/index.html
git commit -m "Pick theme stylesheet from localStorage before first paint"
```

---

### Task 3: Add the toggle to the menu bar, and re-theme the FSM canvas (`App.jsx`, `PlanPage.jsx`)

**Files:**
- Modify: `gcs/react/prime/src/App.jsx`
- Modify: `gcs/react/prime/src/PlanPage.jsx`

**Interfaces:**
- Consumes: `document.getElementById('theme-link')` produced by Task 2; theme asset paths produced by Task 1.
- Produces: `theme` state (`'dark' | 'light'`) and `setTheme` in `App.jsx`, passed down as the `theme` prop to `<PlanPage>` and from there to `<FsmCanvas>`, which forwards it directly to `<ReactFlow colorMode={theme}>`.

This task does **not** touch `overlayContent` (the gear icon's popover containing the "Connection Mode" `SelectButton`, ~line 446) — the new switch sits in the menu bar itself, next to the gear button, not inside the popover.

- [ ] **Step 1: Import `InputSwitch`**

Add after the existing `SelectButton` import (line 15):
```js
import { InputSwitch } from 'primereact/inputswitch';
```

- [ ] **Step 2: Add theme state**

Add after the existing `useLocalVehicle` state (line 61):
```js
const [theme, setTheme] = useState(() => localStorage.getItem('se-theme') || 'dark');
```

- [ ] **Step 3: Add the sync effect**

Add anywhere at the top level of the `App` function body (e.g. directly below the state declarations from Step 2):
```js
useEffect(() => {
    document.getElementById('theme-link').href = `/themes/lara-${theme}-amber/theme.css`;
    localStorage.setItem('se-theme', theme);
}, [theme]);
```

- [ ] **Step 4: Add the switch to `menuBarEnd`**

Current code (~line 473-480):
```jsx
  const menuBarEnd = useMemo(() => (
    <div className="flex align-items-center gap-2 mr-2">
      <GameControls setAxis={setGamePadAxis} setButton={setGamePadButton} deadzone={gamepadDeadzone} />
      <Button size="small" rounded text label="" icon="pi pi-cog" onClick={(e) => op.current.toggle(e)} />
      <OverlayPanel ref={op}>{overlayContent}</OverlayPanel>

    </div>
  ), [useLocalVehicle, gamepadDeadzone, overlayContent]);
```

Replace with:
```jsx
  const menuBarEnd = useMemo(() => (
    <div className="flex align-items-center gap-2 mr-2">
      <GameControls setAxis={setGamePadAxis} setButton={setGamePadButton} deadzone={gamepadDeadzone} />
      <i className="pi pi-moon" />
      <InputSwitch checked={theme === 'light'} onChange={(e) => setTheme(e.value ? 'light' : 'dark')} />
      <i className="pi pi-sun" />
      <Button size="small" rounded text label="" icon="pi pi-cog" onClick={(e) => op.current.toggle(e)} />
      <OverlayPanel ref={op}>{overlayContent}</OverlayPanel>

    </div>
  ), [theme, useLocalVehicle, gamepadDeadzone, overlayContent]);
```
(`theme` is added to the dependency array since the JSX now reads it.)

- [ ] **Step 5: Thread `theme` down to the FSM canvas (`PlanPage.jsx`)**

The Plan tab's canvas is `@xyflow/react`'s `<ReactFlow>`, which has its own `colorMode` prop (`'light' | 'dark' | 'system'`) controlling the minimap, edges, and background dot colors — separate from the PrimeReact CSS swap. It's currently hardcoded to `"dark"` inside `FsmCanvas`, the inner component `PlanPage` renders. Our `theme` values match `colorMode`'s accepted values exactly, so this is a straight pass-through in three places:

In `App.jsx`, update the `<PlanPage>` call site (current code, line 522):
```jsx
{planMounted && <PlanPage vehicles={vehicles} squadList={squadList} />}
```
to:
```jsx
{planMounted && <PlanPage vehicles={vehicles} squadList={squadList} theme={theme} />}
```

In `PlanPage.jsx`, update the component signature (current code, line 354):
```js
function PlanPage({ vehicles, squadList }) {
```
to:
```js
function PlanPage({ vehicles, squadList, theme }) {
```

Still in `PlanPage.jsx`, pass `theme` through to `<FsmCanvas>` (current code, lines 770-780):
```jsx
                                <FsmCanvas
                                    nodes={nodesWithWarnings} edges={edges}
                                    setNodes={setNodes} setEdges={setEdges}
                                    eventInstances={eventInstances} setEventInstances={setEventInstances}
                                    startNodeId={startNodeId} setStartNodeId={setStartNodeId}
                                    schema={schema} features={features}
                                    panelNode={panelNode} setPanelNode={setPanelNodeId}
                                    setPanelEdgeId={setPanelEdgeId}
                                    pushSnapshot={pushSnapshot}
                                    toast={toast}
                                />
```
to:
```jsx
                                <FsmCanvas
                                    nodes={nodesWithWarnings} edges={edges}
                                    setNodes={setNodes} setEdges={setEdges}
                                    eventInstances={eventInstances} setEventInstances={setEventInstances}
                                    startNodeId={startNodeId} setStartNodeId={setStartNodeId}
                                    schema={schema} features={features}
                                    panelNode={panelNode} setPanelNode={setPanelNodeId}
                                    setPanelEdgeId={setPanelEdgeId}
                                    pushSnapshot={pushSnapshot}
                                    toast={toast}
                                    theme={theme}
                                />
```

Finally, update the `FsmCanvas` signature and its `<ReactFlow>` element. Current code (lines 153-155 and 268-269):
```js
function FsmCanvas({ nodes, edges, setNodes, setEdges, eventInstances, setEventInstances,
                     startNodeId, setStartNodeId, schema, features, panelNode, setPanelNode,
                     setPanelEdgeId, pushSnapshot, toast }) {
```
```jsx
            <ReactFlow
                colorMode="dark"
```
to:
```js
function FsmCanvas({ nodes, edges, setNodes, setEdges, eventInstances, setEventInstances,
                     startNodeId, setStartNodeId, schema, features, panelNode, setPanelNode,
                     setPanelEdgeId, pushSnapshot, toast, theme }) {
```
```jsx
            <ReactFlow
                colorMode={theme}
```

- [ ] **Step 6: Start the dev server and headless Chrome**

```bash
cd gcs/react/prime && npx vite --port 5179 --strictPort > /tmp/vite-theme.log 2>&1 &
sleep 2
google-chrome --headless=new --disable-gpu --no-sandbox --remote-debugging-port=9333 --remote-allow-origins=* about:blank > /tmp/chrome-theme.log 2>&1 &
sleep 2 && curl -s http://localhost:9333/json/version
```
Expected: JSON containing `"webSocketDebuggerUrl"`.

- [ ] **Step 7: Write the switch-interaction verification script**

This also mounts the Plan tab and checks that the FSM canvas's `.react-flow` root element drops its `dark` class when the switch flips to light — confirming `colorMode` is actually following `theme`.

Save as `/tmp/verify-theme-switch.mjs`:
```js
const CDP = 'http://localhost:9333';

function connect(wsUrl) {
    return new Promise((resolve, reject) => {
        const ws = new WebSocket(wsUrl);
        ws.addEventListener('open', () => resolve(ws));
        ws.addEventListener('error', reject);
    });
}
function send(ws, method, params = {}) {
    const id = Math.floor(Math.random() * 1e9);
    return new Promise((resolve) => {
        const handler = (ev) => {
            const msg = JSON.parse(ev.data);
            if (msg.id === id) { ws.removeEventListener('message', handler); resolve(msg.result); }
        };
        ws.addEventListener('message', handler);
        ws.send(JSON.stringify({ id, method, params }));
    });
}
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function clickSelector(ws, expression) {
    const r = await send(ws, 'Runtime.evaluate', {
        expression: `(function(){ const el = ${expression}; const r = el.getBoundingClientRect(); return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2}); })()`,
        returnByValue: true,
    });
    const { x, y } = JSON.parse(r.result.value);
    await send(ws, 'Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
    await send(ws, 'Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
}

async function main() {
    const res = await fetch(`${CDP}/json/new?http://localhost:5179/`, { method: 'PUT' });
    const tab = await res.json();
    const ws = await connect(tab.webSocketDebuggerUrl);
    await send(ws, 'Page.enable');
    await send(ws, 'Runtime.enable');
    await sleep(1500);

    // Mount the Plan tab's FSM canvas
    await clickSelector(ws, `Array.from(document.querySelectorAll('.p-menuitem-text')).find(el => el.textContent === 'Plan').closest('.p-menuitem-link')`);
    await sleep(500);

    const beforeToggle = await send(ws, 'Runtime.evaluate', {
        expression: `document.querySelector('.react-flow').classList.contains('dark')`,
        returnByValue: true,
    });
    console.log('CANVAS HAS .dark BEFORE TOGGLE (expect true):', beforeToggle.result.value);

    await clickSelector(ws, `document.querySelector('.p-inputswitch')`);
    await sleep(300);

    const afterClick = await send(ws, 'Runtime.evaluate', {
        expression: `JSON.stringify({href: document.getElementById('theme-link').href, stored: localStorage.getItem('se-theme'), checked: document.querySelector('.p-inputswitch').classList.contains('p-inputswitch-checked'), canvasDark: document.querySelector('.react-flow').classList.contains('dark')})`,
        returnByValue: true,
    });
    console.log('AFTER CLICKING SWITCH:', afterClick.result.value);

    await send(ws, 'Page.reload', {});
    await sleep(1500);
    await clickSelector(ws, `Array.from(document.querySelectorAll('.p-menuitem-text')).find(el => el.textContent === 'Plan').closest('.p-menuitem-link')`);
    await sleep(500);
    const afterReload = await send(ws, 'Runtime.evaluate', {
        expression: `JSON.stringify({href: document.getElementById('theme-link').href, checked: document.querySelector('.p-inputswitch').classList.contains('p-inputswitch-checked'), canvasDark: document.querySelector('.react-flow').classList.contains('dark')})`,
        returnByValue: true,
    });
    console.log('AFTER RELOAD (should persist):', afterReload.result.value);

    ws.close();
    process.exit(0);
}
main().catch(e => { console.error(e); process.exit(1); });
```

- [ ] **Step 8: Run it**

```bash
node /tmp/verify-theme-switch.mjs
```
Expected output (starting from a browser profile where `se-theme` is not already `'light'` — if Task 2's test left it set to `'dark'`, this is satisfied):
```
CANVAS HAS .dark BEFORE TOGGLE (expect true): true
AFTER CLICKING SWITCH: {"href":"http://localhost:5179/themes/lara-light-amber/theme.css","stored":"light","checked":true,"canvasDark":false}
AFTER RELOAD (should persist): {"href":"http://localhost:5179/themes/lara-light-amber/theme.css","checked":true,"canvasDark":false}
```

- [ ] **Step 9: Visually confirm the light theme renders correctly**

```bash
node -e "
const CDP = 'http://localhost:9333';
(async () => {
  const res = await fetch(CDP + '/json/new?http://localhost:5179/');
  const tab = await res.json();
  const ws = new WebSocket(tab.webSocketDebuggerUrl);
  await new Promise(r => ws.addEventListener('open', r));
  function send(method, params={}) {
    const id = Math.floor(Math.random()*1e9);
    return new Promise(resolve => {
      const h = ev => { const m = JSON.parse(ev.data); if (m.id===id){ws.removeEventListener('message',h); resolve(m.result);} };
      ws.addEventListener('message', h);
      ws.send(JSON.stringify({id, method, params}));
    });
  }
  await send('Page.enable');
  await new Promise(r => setTimeout(r, 1500));
  const shot = await send('Page.captureScreenshot', { format: 'png' });
  require('fs').writeFileSync('/tmp/light-theme.png', Buffer.from(shot.data, 'base64'));
  ws.close();
})();
"
```
Then view `/tmp/light-theme.png` (e.g. with the Read tool) and confirm: page background is light, all text is readable (no light-on-light or dark-on-dark contrast failures), and the moon/switch/sun control is visible next to the gear icon in the menu bar.

- [ ] **Step 10: Confirm no regression in the numeric-input panels under light theme**

The most recent change to this app fixed decimal-entry and field-clearing bugs in `FieldInput.jsx`'s `InputNumber` usage (task/edge parameter panels). Rather than driving the full Plan canvas (React Flow node positions are dynamic and not worth scripting for a visual check), mount `FieldInput` directly in a throwaway harness with the light theme stylesheet linked.

Save as `gcs/react/prime/verify.html`:
```html
<!doctype html>
<html>
  <head>
    <link rel="stylesheet" href="/themes/lara-light-amber/theme.css">
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/verify-main.jsx"></script>
  </body>
</html>
```

Save as `gcs/react/prime/src/verify-main.jsx`:
```jsx
import React from 'react';
import { createRoot } from 'react-dom/client';
import 'primereact/resources/primereact.min.css';
import 'primeicons/primeicons.css';
import 'primeflex/primeflex.css';
import FieldInput from './FieldInput.jsx';

function Harness() {
    const [errTol, setErrTol] = React.useState(undefined);
    const [altCeil, setAltCeil] = React.useState(undefined);
    return (
        <div style={{ width: 320, padding: 8 }}>
            <div>
                <label style={{ fontSize: 13, display: 'block', marginBottom: 4 }}>err_tol</label>
                <FieldInput field={{ name: 'err_tol', type: 'number', default: 1.0 }} value={errTol} onChange={setErrTol} />
            </div>
            <div style={{ marginTop: 12 }}>
                <label style={{ fontSize: 13, display: 'block', marginBottom: 4 }}>altitude_ceil</label>
                <FieldInput field={{ name: 'altitude_ceil', type: 'number', default: 10.0 }} value={altCeil} onChange={setAltCeil} />
            </div>
        </div>
    );
}

createRoot(document.getElementById('root')).render(<Harness />);
```

Screenshot it:
```bash
node -e "
const CDP = 'http://localhost:9333';
(async () => {
  const res = await fetch(CDP + '/json/new?http://localhost:5179/verify.html');
  const tab = await res.json();
  const ws = new WebSocket(tab.webSocketDebuggerUrl);
  await new Promise(r => ws.addEventListener('open', r));
  function send(method, params={}) {
    const id = Math.floor(Math.random()*1e9);
    return new Promise(resolve => {
      const h = ev => { const m = JSON.parse(ev.data); if (m.id===id){ws.removeEventListener('message',h); resolve(m.result);} };
      ws.addEventListener('message', h);
      ws.send(JSON.stringify({id, method, params}));
    });
  }
  await send('Page.enable');
  await new Promise(r => setTimeout(r, 1200));
  const shot = await send('Page.captureScreenshot', { format: 'png' });
  require('fs').writeFileSync('/tmp/light-theme-fields.png', Buffer.from(shot.data, 'base64'));
  ws.close();
})();
"
```
View `/tmp/light-theme-fields.png` (e.g. with the Read tool) and confirm both fields render with dark, readable text on the light theme's input background — no invisible or low-contrast text.

Delete the throwaway harness afterward (it must not be committed):
```bash
rm -f gcs/react/prime/verify.html gcs/react/prime/src/verify-main.jsx /tmp/light-theme-fields.png
```

- [ ] **Step 11: Stop processes and clean up**

```bash
pkill -f "remote-debugging-port=9333"
pkill -f "vite --port 5179"
rm -f /tmp/verify-theme-switch.mjs /tmp/light-theme.png /tmp/vite-theme.log /tmp/chrome-theme.log
```

- [ ] **Step 12: Commit**

```bash
git add gcs/react/prime/src/App.jsx gcs/react/prime/src/PlanPage.jsx
git commit -m "Add light/dark theme toggle, synced across PrimeReact and the FSM canvas"
```
