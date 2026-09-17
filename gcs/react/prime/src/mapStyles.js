// Shared Mapbox basemap style options, used by both the Plan page's Map
// tab (MapDraw.jsx) and the Control page's map header (ControlPage.jsx /
// Mapbox.jsx) so the two dropdowns can't drift apart.

export const STYLE_URLS = {
    streets: 'mapbox://styles/mapbox/standard',
    satellite: 'mapbox://styles/mapbox/satellite-streets-v12',
};

export const STYLE_OPTIONS = [
    { label: 'Streets', value: 'streets' },
    { label: 'Satellite', value: 'satellite' },
];

// Mapbox Standard's basemap config schema (queried from the style itself --
// see mapbox://styles/mapbox/standard's top-level "schema" field) defaults
// almost every label/3D-object toggle to true, which buries the vehicle
// markers under POI pins, place names, and landmark icons. Road labels are
// kept for orientation (left out here, at their default of true), and so
// are 3D buildings -- useful for judging line-of-sight/obstacles under the
// Streets tileset -- while 3D trees/landmarks stay off since those add
// clutter without much orientation value.
export const BASEMAP_CONFIG_FLAGS = {
    showPedestrianRoads: false,
    showTransitLabels: false,
    showAdminBoundaries: false,
    showPointOfInterestLabels: false,
    showPlaceLabels: false,
    showLandmarkIcons: false,
    showLandmarkIconLabels: false,
    show3dObjects: true,
    show3dBuildings: true,
    show3dTrees: false,
    show3dLandmarks: false,
};

// The Map constructor's `config` option silently fails to apply against
// the Standard style in this mapbox-gl-js version (verified empirically --
// config values read back as schema defaults even though the documented
// `config: { basemap: {...} }` constructor shape was used). Calling
// setConfigProperty imperatively after the style has parsed does work, so
// callers apply this from a 'style.load' handler instead -- which also
// means it's naturally reapplied after setStyle() switches the basemap.
// It's a silent no-op on styles without a 'basemap' schema (e.g. the
// classic satellite-streets style), so it's safe to call unconditionally.
export function applyBasemapConfig(map) {
    Object.entries(BASEMAP_CONFIG_FLAGS).forEach(([key, value]) => {
        map.setConfigProperty('basemap', key, value);
    });
}

// satellite-streets-v12 is a classic (pre-Standard) style with its own
// fixed vector layers rather than a config schema, so the flags above are
// a no-op against it -- its POI/place/transit/airport labels need to be
// hidden by layer id instead. Road labels/shields are left alone, same
// policy as BASEMAP_CONFIG_FLAGS's showRoadLabels.
const SATELLITE_HIDDEN_LAYERS = [
    'poi-label',
    'transit-label',
    'airport-label',
    'settlement-subdivision-label',
    'settlement-minor-label',
    'settlement-major-label',
];

// Guarded per-layer with getLayer() (rather than relying on setLayoutProperty
// to no-op) since it throws on an unknown layer id -- e.g. when called
// against the Standard style, which has none of these classic layer ids.
export function applySatelliteLayerVisibility(map) {
    SATELLITE_HIDDEN_LAYERS.forEach((id) => {
        if (map.getLayer(id)) {
            map.setLayoutProperty(id, 'visibility', 'none');
        }
    });
}
