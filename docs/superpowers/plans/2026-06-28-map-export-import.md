# Map Export / Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Import / Export GeoJSON / Export KML buttons to the MapDraw component so users can save and reload polygons drawn on the mission map.

**Architecture:** All changes are contained in `MapDraw.jsx` and a new `mapUtils.js` pure-function module. Conversion logic is extracted into `mapUtils.js` so it can be unit-tested. `PlanPage.jsx` passes its existing `toast` ref down to `MapDraw` so import errors surface in the same toast used everywhere else.

**Tech Stack:** React 19, MapboxDraw, `tokml` (already installed), `@tmcw/togeojson` (new), Vitest + jsdom (jsdom new)

## Global Constraints

- All source files live under `gcs/react/prime/src/`
- Run tests with: `cd gcs/react/prime && npx vitest run`
- PrimeReact `<Button>` with `size="small" outlined` for toolbar buttons (matches existing toolbar style)
- Export filenames: `map-features.geojson` and `map-features.kml`
- Import replaces ALL existing features (no merging)
- File format detected by extension: `.kml`, `.geojson`, `.json` (case-insensitive)
- Toast errors via the `toast` ref passed from PlanPage — `toast.current.show({ severity: 'error', summary: '...', detail: e.message })`

---

### Task 1: Install new dependencies

**Files:**
- Modify: `gcs/react/prime/package.json`

**Interfaces:**
- Produces: `@tmcw/togeojson` importable as `import { kml } from '@tmcw/togeojson'`; `jsdom` available as vitest environment

- [ ] **Step 1: Install runtime and dev dependencies**

```bash
cd gcs/react/prime
npm install @tmcw/togeojson
npm install --save-dev jsdom
```

Expected output: both packages appear in `package.json` dependencies/devDependencies.

- [ ] **Step 2: Verify install**

```bash
cd gcs/react/prime && node -e "import('@tmcw/togeojson').then(m => console.log('ok', Object.keys(m)))"
```

Expected: `ok [ 'kml', 'gpx', 'tcx', ... ]`

- [ ] **Step 3: Commit**

```bash
cd gcs/react/prime
git add package.json package-lock.json
git commit -m "feat: add @tmcw/togeojson and jsdom for map import"
```

---

### Task 2: Create `mapUtils.js` with conversion/parsing functions + tests

**Files:**
- Create: `gcs/react/prime/src/mapUtils.js`
- Create: `gcs/react/prime/src/mapUtils.test.js`

**Interfaces:**
- Produces:
  - `featuresToGeoJson(featuresJson: string): string` — pretty-prints the FeatureCollection JSON
  - `featuresToKml(featuresJson: string): string` — converts FeatureCollection JSON to KML string
  - `parseImportFile(filename: string, text: string): GeoJSON.FeatureCollection` — parses KML or GeoJSON text; throws `Error` with a user-readable message on failure

- [ ] **Step 1: Write the failing tests**

Create `gcs/react/prime/src/mapUtils.test.js`:

```js
// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { featuresToGeoJson, featuresToKml, parseImportFile } from './mapUtils.js';

const SAMPLE_FC = {
    type: 'FeatureCollection',
    features: [{
        type: 'Feature',
        geometry: {
            type: 'Polygon',
            coordinates: [[
                [-79.94, 40.44], [-79.93, 40.44],
                [-79.93, 40.45], [-79.94, 40.44],
            ]],
        },
        properties: { name: 'TestArea' },
    }],
};
const SAMPLE_FC_JSON = JSON.stringify(SAMPLE_FC);

const SAMPLE_KML = `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>TestArea</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>-79.94,40.44,0 -79.93,40.44,0 -79.93,40.45,0 -79.94,40.44,0</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>`;

describe('featuresToGeoJson', () => {
    it('round-trips a FeatureCollection', () => {
        const result = featuresToGeoJson(SAMPLE_FC_JSON);
        expect(JSON.parse(result)).toEqual(SAMPLE_FC);
    });

    it('pretty-prints the output', () => {
        const result = featuresToGeoJson(SAMPLE_FC_JSON);
        expect(result).toContain('\n');
    });
});

describe('featuresToKml', () => {
    it('produces a KML string with a Placemark', () => {
        const result = featuresToKml(SAMPLE_FC_JSON);
        expect(result).toContain('<kml');
        expect(result).toContain('<Placemark');
    });
});

describe('parseImportFile', () => {
    it('parses a valid .geojson file', () => {
        const fc = parseImportFile('areas.geojson', SAMPLE_FC_JSON);
        expect(fc.type).toBe('FeatureCollection');
        expect(fc.features).toHaveLength(1);
    });

    it('parses a .json file as GeoJSON', () => {
        const fc = parseImportFile('areas.json', SAMPLE_FC_JSON);
        expect(fc.type).toBe('FeatureCollection');
    });

    it('parses a valid .kml file and returns a FeatureCollection', () => {
        const fc = parseImportFile('areas.kml', SAMPLE_KML);
        expect(fc.type).toBe('FeatureCollection');
        expect(fc.features.length).toBeGreaterThan(0);
    });

    it('throws on unsupported extension', () => {
        expect(() => parseImportFile('data.csv', '{}')).toThrow('Unsupported file type');
    });

    it('throws on malformed GeoJSON', () => {
        expect(() => parseImportFile('bad.geojson', 'not json')).toThrow();
    });

    it('throws when GeoJSON root is not a FeatureCollection', () => {
        const notFc = JSON.stringify({ type: 'Feature', geometry: null, properties: {} });
        expect(() => parseImportFile('bad.geojson', notFc)).toThrow('Not a valid GeoJSON FeatureCollection');
    });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd gcs/react/prime && npx vitest run src/mapUtils.test.js
```

Expected: all tests fail with `Cannot find module './mapUtils.js'`

- [ ] **Step 3: Implement `mapUtils.js`**

Create `gcs/react/prime/src/mapUtils.js`:

```js
import tokml from 'tokml';
import { kml as kmlToGeoJson } from '@tmcw/togeojson';

export function featuresToGeoJson(featuresJson) {
    return JSON.stringify(JSON.parse(featuresJson), null, 2);
}

export function featuresToKml(featuresJson) {
    return tokml(JSON.parse(featuresJson));
}

export function parseImportFile(filename, text) {
    const ext = filename.split('.').pop().toLowerCase();
    if (ext === 'kml') {
        const dom = new DOMParser().parseFromString(text, 'text/xml');
        const fc = kmlToGeoJson(dom);
        if (!fc || fc.type !== 'FeatureCollection') {
            throw new Error('KML did not produce a valid FeatureCollection');
        }
        return fc;
    }
    if (ext === 'geojson' || ext === 'json') {
        const fc = JSON.parse(text);
        if (!fc || fc.type !== 'FeatureCollection' || !Array.isArray(fc.features)) {
            throw new Error('Not a valid GeoJSON FeatureCollection');
        }
        return fc;
    }
    throw new Error('Unsupported file type. Use .kml, .geojson, or .json');
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd gcs/react/prime && npx vitest run src/mapUtils.test.js
```

Expected: all 8 tests pass

- [ ] **Step 5: Run the full test suite to confirm no regressions**

```bash
cd gcs/react/prime && npx vitest run
```

Expected: all tests pass (validation tests + new mapUtils tests)

- [ ] **Step 6: Commit**

```bash
cd gcs/react/prime
git add src/mapUtils.js src/mapUtils.test.js
git commit -m "feat: add mapUtils with GeoJSON/KML conversion functions"
```

---

### Task 3: Add export buttons to MapDraw + pass toast prop from PlanPage

**Files:**
- Modify: `gcs/react/prime/src/MapDraw.jsx`
- Modify: `gcs/react/prime/src/PlanPage.jsx:858-862`

**Interfaces:**
- Consumes: `featuresToGeoJson(featuresJson)`, `featuresToKml(featuresJson)` from `./mapUtils.js`
- Produces: `MapDraw` now accepts a `toast` prop (React ref pointing to a PrimeReact Toast instance)

- [ ] **Step 1: Update `MapDraw.jsx` to accept `toast` prop, add `useMemo`, import mapUtils, and add export handlers**

Replace the top of `MapDraw.jsx` (imports + function signature) and the return block. Full new file content:

```jsx
import { useState, useRef, useEffect, useMemo } from 'react';
import mapboxgl from 'mapbox-gl';
import MapboxDraw from '@mapbox/mapbox-gl-draw';
import 'mapbox-gl/dist/mapbox-gl.css';
import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';
import { MAPBOX_TOKEN } from './config.js';
import { InputText } from 'primereact/inputtext';
import { Button } from 'primereact/button';
import { featuresToGeoJson, featuresToKml } from './mapUtils.js';

function MapDraw({ features, setFeatures, toast }) {
    const mapRef = useRef();
    const mapContainerRef = useRef();
    const draw = useRef();
    const numFeaturesRef = useRef(0);

    const [selectedFeatureId, setSelectedFeatureId] = useState(null);
    const [nameInput, setNameInput] = useState('');

    const hasFeatures = useMemo(() => {
        try { return JSON.parse(features).features.length > 0; } catch { return false; }
    }, [features]);

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
        const ro = new ResizeObserver(() => { mapRef.current?.resize(); });
        ro.observe(mapContainerRef.current);

        return () => { clearTimeout(timer); ro.disconnect(); mapRef.current.remove(); };
    }, []);

    function applyName() {
        if (!selectedFeatureId) return;
        const feat = draw.current.get(selectedFeatureId);
        if (!feat) return;
        feat.properties = { ...(feat.properties || {}), name: nameInput };
        draw.current.add(feat);
        setFeatures(JSON.stringify(draw.current.getAll()));
    }

    function handleExportGeoJson() {
        const blob = new Blob([featuresToGeoJson(features)], { type: 'application/geo+json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'map-features.geojson';
        a.click();
        URL.revokeObjectURL(url);
    }

    function handleExportKml() {
        const blob = new Blob([featuresToKml(features)], { type: 'application/vnd.google-earth.kml+xml' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'map-features.kml';
        a.click();
        URL.revokeObjectURL(url);
    }

    return (
        <div className="flex flex-column" style={{ height: '100%' }}>
            <div className="flex gap-2 align-items-center p-2" style={{ borderBottom: '1px solid #2a3a4a' }}>
                <Button
                    label="Export GeoJSON"
                    icon="pi pi-file"
                    size="small"
                    outlined
                    disabled={!hasFeatures}
                    onClick={handleExportGeoJson}
                />
                <Button
                    label="Export KML"
                    icon="pi pi-file-export"
                    size="small"
                    outlined
                    disabled={!hasFeatures}
                    onClick={handleExportKml}
                />
                {selectedFeatureId && (
                    <div className="flex gap-2 align-items-center" style={{ marginLeft: 'auto' }}>
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
            </div>
            <div id="map-container" ref={mapContainerRef} style={{ flex: 1 }} />
        </div>
    );
}

export default MapDraw;
```

- [ ] **Step 2: Pass `toast` to `<MapDraw>` in `PlanPage.jsx`**

In `PlanPage.jsx` at line 860, the MapDraw usage currently reads:
```jsx
<MapDraw features={features} setFeatures={setFeatures} />
```

Change it to:
```jsx
<MapDraw features={features} setFeatures={setFeatures} toast={toast} />
```

- [ ] **Step 3: Run tests to confirm nothing broke**

```bash
cd gcs/react/prime && npx vitest run
```

Expected: all tests pass

- [ ] **Step 4: Manual smoke test — export**

Start the dev server (`npm run dev` in `gcs/react/prime`). Open the GCS in a browser:

1. Switch to the **Map** tab
2. Draw two polygons
3. Click **Export GeoJSON** — browser should download `map-features.geojson`; open the file and confirm it contains a valid FeatureCollection with 2 features
4. Click **Export KML** — browser should download `map-features.kml`; open the file and confirm it contains `<kml>` and two `<Placemark>` elements
5. With no features drawn (clear the map first), confirm both export buttons are **disabled**

- [ ] **Step 5: Commit**

```bash
cd gcs/react/prime
git add src/MapDraw.jsx src/PlanPage.jsx
git commit -m "feat: add GeoJSON and KML export to MapDraw"
```

---

### Task 4: Add import to MapDraw

**Files:**
- Modify: `gcs/react/prime/src/MapDraw.jsx`

**Interfaces:**
- Consumes: `parseImportFile(filename, text)` from `./mapUtils.js`
- Consumes: `toast` prop (already wired in Task 3)

- [ ] **Step 1: Add `parseImportFile` to the import in `MapDraw.jsx`**

Change the mapUtils import line from:
```js
import { featuresToGeoJson, featuresToKml } from './mapUtils.js';
```
to:
```js
import { featuresToGeoJson, featuresToKml, parseImportFile } from './mapUtils.js';
```

- [ ] **Step 2: Add the `importFileRef` ref and `handleImport` function**

After the `draw` ref declaration (`const draw = useRef();`), add:
```js
const importFileRef = useRef(null);
```

After `handleExportKml`, add:
```js
async function handleImport(file) {
    if (!file) return;
    try {
        const text = await file.text();
        const fc = parseImportFile(file.name, text);
        draw.current.deleteAll();
        draw.current.set(fc);
        numFeaturesRef.current = fc.features.length;
        setFeatures(JSON.stringify(draw.current.getAll()));
    } catch (e) {
        toast.current.show({ severity: 'error', summary: 'Import failed', detail: e.message });
    } finally {
        if (importFileRef.current) importFileRef.current.value = '';
    }
}
```

- [ ] **Step 3: Add the hidden file input and Import button to the toolbar**

In the return block, update the toolbar `<div>` to add the file input and Import button before the export buttons:

```jsx
<div className="flex gap-2 align-items-center p-2" style={{ borderBottom: '1px solid #2a3a4a' }}>
    <input
        ref={importFileRef}
        type="file"
        accept=".kml,.geojson,.json"
        style={{ display: 'none' }}
        onChange={e => handleImport(e.target.files[0])}
    />
    <Button
        label="Import"
        icon="pi pi-upload"
        size="small"
        outlined
        onClick={() => importFileRef.current?.click()}
    />
    <Button
        label="Export GeoJSON"
        icon="pi pi-file"
        size="small"
        outlined
        disabled={!hasFeatures}
        onClick={handleExportGeoJson}
    />
    <Button
        label="Export KML"
        icon="pi pi-file-export"
        size="small"
        outlined
        disabled={!hasFeatures}
        onClick={handleExportKml}
    />
    {selectedFeatureId && (
        <div className="flex gap-2 align-items-center" style={{ marginLeft: 'auto' }}>
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
</div>
```

- [ ] **Step 4: Run tests to confirm nothing broke**

```bash
cd gcs/react/prime && npx vitest run
```

Expected: all tests pass

- [ ] **Step 5: Manual smoke test — import round-trip**

With the dev server running:

1. Draw two polygons on the map and name them "AreaA" and "AreaB"
2. Click **Export GeoJSON** and save the file
3. Click **Export KML** and save the file
4. Draw a third polygon (to confirm it gets replaced)
5. Click **Import**, select the saved `.geojson` file — map should replace all features with the two original polygons; area names should be preserved
6. Draw a third polygon again, then click **Import** with the saved `.kml` file — same result: replaced with the two original polygons
7. Click **Import**, select a `.txt` file — toast error should appear: "Import failed" / "Unsupported file type. Use .kml, .geojson, or .json"
8. Create a file named `bad.geojson` containing `{not valid json}`, import it — toast error: "Import failed" / parse error message
9. Confirm that after a successful import, drawing a new polygon generates a non-conflicting ID (the polygon appears correctly, no console errors)

- [ ] **Step 6: Commit**

```bash
cd gcs/react/prime
git add src/MapDraw.jsx
git commit -m "feat: add KML and GeoJSON import to MapDraw"
```
