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

export function featureLabel(feature, index) {
    if (feature.properties?.name) return feature.properties.name;
    return `${feature.geometry?.type ?? 'Feature'} ${index + 1}`;
}

export function lineMidpoint(coordinates) {
    if (coordinates.length === 1) return coordinates[0];
    const segLengths = [];
    let total = 0;
    for (let i = 0; i < coordinates.length - 1; i++) {
        const [x1, y1] = coordinates[i];
        const [x2, y2] = coordinates[i + 1];
        const d = Math.hypot(x2 - x1, y2 - y1);
        segLengths.push(d);
        total += d;
    }
    let target = total / 2;
    for (let i = 0; i < segLengths.length; i++) {
        if (target <= segLengths[i]) {
            const t = segLengths[i] === 0 ? 0 : target / segLengths[i];
            const [x1, y1] = coordinates[i];
            const [x2, y2] = coordinates[i + 1];
            return [x1 + (x2 - x1) * t, y1 + (y2 - y1) * t];
        }
        target -= segLengths[i];
    }
    return coordinates[coordinates.length - 1];
}

export function polygonCentroid(coordinates) {
    const ring = coordinates[0];
    let area = 0, cx = 0, cy = 0;
    for (let i = 0; i < ring.length - 1; i++) {
        const [x0, y0] = ring[i];
        const [x1, y1] = ring[i + 1];
        const cross = x0 * y1 - x1 * y0;
        area += cross;
        cx += (x0 + x1) * cross;
        cy += (y0 + y1) * cross;
    }
    area *= 0.5;
    if (area === 0) {
        const n = ring.length - 1;
        return ring.slice(0, n).reduce((acc, [x, y]) => [acc[0] + x / n, acc[1] + y / n], [0, 0]);
    }
    return [cx / (6 * area), cy / (6 * area)];
}

export function labelAnchor(feature) {
    const { type, coordinates } = feature.geometry;
    if (type === 'Point') return coordinates;
    if (type === 'LineString') return lineMidpoint(coordinates);
    if (type === 'Polygon') return polygonCentroid(coordinates);
    return null;
}
