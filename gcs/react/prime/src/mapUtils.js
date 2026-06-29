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
