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
