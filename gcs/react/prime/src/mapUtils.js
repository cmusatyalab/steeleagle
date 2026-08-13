import tokml from 'tokml';
import { kml as kmlToGeoJson } from '@tmcw/togeojson';
import ColorHash from 'color-hash';

const colorHash = new ColorHash();

export function vehicleColor(name) {
    return colorHash.hex(name);
}

export function vehicleSpeed(velocity) {
    if (!velocity) return 0;
    return Math.sqrt(velocity.x_vel ** 2 + velocity.y_vel ** 2 + velocity.z_vel ** 2);
}

// Matches the "Disconnected" threshold already used by the status card.
export function isVehicleDisconnected(vehicle) {
    return vehicle.last_updated > 5;
}

// A single source of truth for "what state is this vehicle in," reused by
// every place that renders a vehicle's status. Offline overrides
// selection -- a vehicle that stopped reporting isn't meaningfully
// "selected" for control purposes.
export function vehicleStatus(disconnected, selected) {
    if (disconnected) return 'offline';
    if (selected) return 'selected';
    return 'online';
}

// Sidebar card border/tint, collapsed rail dot, and map marker/popup all
// key off this triad so the three states read the same way everywhere:
// red = offline, blue = online-but-not-selected, green = selected. Raw
// --red-500/--blue-500/--green-500 (unlike the old muted --gray-* scheme)
// are saturated enough to stay legible on both the light/dark app themes
// and the always-dark map basemap, so no theme- or surface-specific
// tuning is needed here -- confirmed identical hex across lara-dark-amber
// and lara-light-blue theme files.
const SURFACE_STATUS_COLORS = {
    offline: 'var(--red-500)',
    online: 'var(--blue-500)',
    selected: 'var(--green-500)',
};

export function vehicleStatusColor(status) {
    return SURFACE_STATUS_COLORS[status];
}

// Collapsed rail dot fill. "offline" stays a dim grey fill (not red) so it
// still reads as "inactive" at a glance -- vehicleStatusColor's red is used
// only for its ring/border -- while "online"/"selected" fill solid with
// their status color.
export function vehicleStatusRailFill(status) {
    return status === 'offline' ? 'var(--gray-500)' : vehicleStatusColor(status);
}

// Map marker fill, drawn against the dark "dusk" basemap. "offline" stays
// grey (not red) -- red markers scattered across the map read as visually
// busy/alarming next to the basemap and detection markers, whereas the
// sidebar cards (a much smaller, denser area) read fine with the bolder
// red. "online" matches the sidebar card's --blue-500 exactly so a
// vehicle's map marker and its status card read as the same color.
const MAP_STATUS_COLORS = {
    offline: 'var(--gray-500)',
    online: 'var(--blue-500)',
    selected: 'var(--green-500)',
};

export function vehicleStatusMapColor(status) {
    return MAP_STATUS_COLORS[status];
}

// Map popup label text. Deliberately does NOT mirror vehicleStatusMapColor
// -- only the chevron marker itself should carry the blue "online" accent;
// the text underneath stays a neutral grey scale (darker for offline,
// lighter for online) so labels stay easy to read at a glance without
// competing with the marker's color. "selected" is white for contrast
// against its green marker.
const TEXT_STATUS_COLORS = {
    offline: 'var(--gray-500)',
    online: 'var(--gray-200)',
    selected: '#ffffff',
};

export function vehicleStatusTextColor(status) {
    return TEXT_STATUS_COLORS[status];
}

const STATUS_SORT_RANK = { selected: 0, online: 1, offline: 2 };

// Selected vehicles first, then online, then offline (sinks to the
// bottom); alphabetical by name within each group. squadList may be
// null/undefined (no manual selection yet).
export function sortVehiclesForDisplay(vehicles, squadList) {
    const squad = squadList ?? [];
    return [...vehicles].sort((a, b) => {
        const statusA = vehicleStatus(isVehicleDisconnected(a), squad.includes(a.name));
        const statusB = vehicleStatus(isVehicleDisconnected(b), squad.includes(b.name));
        const rankDiff = STATUS_SORT_RANK[statusA] - STATUS_SORT_RANK[statusB];
        if (rankDiff !== 0) return rankDiff;
        return a.name.localeCompare(b.name);
    });
}

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
        if (dom.querySelector('parsererror')) {
            throw new Error('Failed to parse KML: invalid XML');
        }
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

export function bboxFromFeature(feature) {
    const { type, coordinates } = feature.geometry;
    if (type === 'Point') {
        const [lng, lat] = coordinates;
        return [lng - 0.001, lat - 0.001, lng + 0.001, lat + 0.001];
    }
    const coords = type === 'Polygon' ? coordinates[0] : coordinates;
    let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;
    for (const [lng, lat] of coords) {
        if (lng < minLng) minLng = lng;
        if (lat < minLat) minLat = lat;
        if (lng > maxLng) maxLng = lng;
        if (lat > maxLat) maxLat = lat;
    }
    return [minLng, minLat, maxLng, maxLat];
}
