// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { featuresToGeoJson, featuresToKml, parseImportFile, bboxFromFeature, featureLabel } from './mapUtils.js';

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

    it('throws on malformed KML (invalid XML)', () => {
        expect(() => parseImportFile('bad.kml', '<kml><broken')).toThrow('Failed to parse KML');
    });
});

describe('bboxFromFeature', () => {
    it('returns tight bbox for a polygon', () => {
        const feature = {
            type: 'Feature',
            geometry: {
                type: 'Polygon',
                coordinates: [[[-80, 40], [-79, 40], [-79, 41], [-80, 41], [-80, 40]]],
            },
            properties: {},
        };
        expect(bboxFromFeature(feature)).toEqual([-80, 40, -79, 41]);
    });

    it('returns tight bbox for a linestring', () => {
        const feature = {
            type: 'Feature',
            geometry: {
                type: 'LineString',
                coordinates: [[-80, 40], [-79, 41]],
            },
            properties: {},
        };
        expect(bboxFromFeature(feature)).toEqual([-80, 40, -79, 41]);
    });

    it('returns buffered bbox for a point', () => {
        const feature = {
            type: 'Feature',
            geometry: { type: 'Point', coordinates: [-80, 40] },
            properties: {},
        };
        const bbox = bboxFromFeature(feature);
        expect(bbox[0]).toBeCloseTo(-80.001);
        expect(bbox[1]).toBeCloseTo(39.999);
        expect(bbox[2]).toBeCloseTo(-79.999);
        expect(bbox[3]).toBeCloseTo(40.001);
    });
});

describe('featureLabel', () => {
    it('returns the feature name when set', () => {
        const feature = { properties: { name: 'AreaB' }, geometry: { type: 'Polygon' } };
        expect(featureLabel(feature, 0)).toBe('AreaB');
    });

    it('falls back to geometry type and 1-based index when unnamed', () => {
        const feature = { properties: {}, geometry: { type: 'Point' } };
        expect(featureLabel(feature, 2)).toBe('Point 3');
    });

    it('falls back to "Feature" when geometry type is missing', () => {
        const feature = { properties: {}, geometry: null };
        expect(featureLabel(feature, 0)).toBe('Feature 1');
    });

    it('ignores an empty-string name and uses the fallback', () => {
        const feature = { properties: { name: '' }, geometry: { type: 'LineString' } };
        expect(featureLabel(feature, 1)).toBe('LineString 2');
    });
});
