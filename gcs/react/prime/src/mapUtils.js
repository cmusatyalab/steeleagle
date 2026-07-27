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
