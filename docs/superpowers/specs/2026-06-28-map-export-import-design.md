# Map Export / Import Design

**Date:** 2026-06-28
**Status:** Approved

## Overview

Add KML and GeoJSON export/import to the Map tab of the GCS PlanPage so that drawn polygons can be saved to disk and reloaded in a later session. The feature lives entirely in `MapDraw.jsx`, which already owns the MapboxDraw instance (`draw.current`) and calls `setFeatures` to propagate state up to PlanPage.

## Scope

- Export drawn features as **GeoJSON** (raw FeatureCollection JSON download)
- Export drawn features as **KML** (via `tokml`, already installed)
- Import a **GeoJSON or KML** file, replacing all current features on the map
- File format detection by extension (`.kml`, `.geojson`, `.json`)
- KML parsing via `@tmcw/togeojson` (new dependency, browser-compatible)

Out of scope: merging imported features with existing ones; any server-side file handling.

## Dependencies

| Package | Purpose | Already installed? |
|---|---|---|
| `tokml` | GeoJSON → KML | Yes |
| `@tmcw/togeojson` | KML → GeoJSON (browser DOM parser) | No — add to `package.json` |

## Architecture

`features` (GeoJSON FeatureCollection string) is owned by `PlanPage` and passed to `MapDraw` as a prop. `MapDraw` calls `setFeatures` after every draw event. This same `features` prop is used for export. PlanPage also passes its `toast` ref as a prop so MapDraw can surface import errors without owning a separate `<Toast>` component.

Import flow:
1. User clicks **Import** → triggers hidden `<input type="file" accept=".kml,.geojson,.json">`
2. File is read as text
3. If `.kml`: parse DOM with `@tmcw/togeojson`, produce a GeoJSON FeatureCollection
4. If `.geojson` / `.json`: parse directly as JSON
5. `draw.current.deleteAll()`
6. `draw.current.set(featureCollection)`
7. `setFeatures(JSON.stringify(draw.current.getAll()))` — syncs state to PlanPage

Export flow (GeoJSON):
- Serialize `features` prop as a JSON Blob → trigger download as `map-features.geojson`

Export flow (KML):
- `tokml(JSON.parse(features))` → trigger download as `map-features.kml`

## UI

The toolbar row at the top of `MapDraw` is updated to always be visible (currently only shown when a feature is selected). Import/export buttons sit on the left; the existing area-name controls remain on the right and are conditionally rendered when a feature is selected.

```
[ Import ]  [ Export GeoJSON ]  [ Export KML ]          Area name: [___] [ Set ]
```

- **Import** and both **Export** buttons are always visible
- **Export GeoJSON** and **Export KML** are disabled when the feature collection is empty
- **Area name** controls remain visible only when a feature is selected (no change from today)

## Error Handling

| Scenario | Behavior |
|---|---|
| Unsupported file extension | Toast error: "Unsupported file type. Use .kml, .geojson, or .json" |
| Malformed KML | Toast error: "Failed to parse KML: `<exception message>`" |
| Malformed GeoJSON | Toast error: "Failed to parse GeoJSON: `<exception message>`" |
| Empty feature collection | Allowed — clears the map (consistent with "replace" semantics) |
| Export with no features | Export buttons disabled |

Errors use the existing `toast` pattern from PlanPage. Since `MapDraw` does not own a `<Toast>` ref, a `toast` prop will be passed down from PlanPage (same ref already used elsewhere in PlanPage).

## Files Changed

| File | Change |
|---|---|
| `gcs/react/prime/package.json` | Add `@tmcw/togeojson` dependency |
| `gcs/react/prime/src/MapDraw.jsx` | Add import/export handlers, toolbar buttons, hidden file input |
| `gcs/react/prime/src/PlanPage.jsx` | Pass `toast` prop to `<MapDraw>` |
