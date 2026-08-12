// @vitest-environment jsdom
import { describe, it, expect } from 'vitest';
import { featuresToGeoJson, featuresToKml, parseImportFile, bboxFromFeature, vehicleColor, vehicleSpeed, isVehicleDisconnected, vehicleStatus, vehicleStatusColor, vehicleStatusMapColor, vehicleStatusTextColor, sortVehiclesForDisplay } from './mapUtils.js';

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

describe('vehicleColor', () => {
    it('returns a hex color string', () => {
        expect(vehicleColor('vehicle-1')).toMatch(/^#[0-9a-f]{6}$/i);
    });

    it('is deterministic for the same name', () => {
        expect(vehicleColor('vehicle-1')).toBe(vehicleColor('vehicle-1'));
    });

    it('differs for different names', () => {
        expect(vehicleColor('vehicle-1')).not.toBe(vehicleColor('vehicle-2'));
    });
});

describe('vehicleSpeed', () => {
    it('returns 0 for a stationary vehicle', () => {
        expect(vehicleSpeed({ x_vel: 0, y_vel: 0, z_vel: 0 })).toBe(0);
    });

    it('returns the magnitude for a single-axis velocity', () => {
        expect(vehicleSpeed({ x_vel: 3, y_vel: 0, z_vel: 0 })).toBe(3);
    });

    it('computes the Euclidean norm across all three axes', () => {
        // 3-4-12 generalizes the 3-4-5 triple to three dimensions: sqrt(9+16+144) = 13
        expect(vehicleSpeed({ x_vel: 3, y_vel: 4, z_vel: 12 })).toBe(13);
    });

    it('treats negative components the same as positive (speed has no direction)', () => {
        expect(vehicleSpeed({ x_vel: -3, y_vel: -4, z_vel: 0 })).toBe(5);
    });

    it('returns 0 for a null or undefined velocity', () => {
        expect(vehicleSpeed(null)).toBe(0);
        expect(vehicleSpeed(undefined)).toBe(0);
    });
});

describe('isVehicleDisconnected', () => {
    it('is false when telemetry was just seen', () => {
        expect(isVehicleDisconnected({ last_updated: 0 })).toBe(false);
    });

    it('is false right at the boundary', () => {
        expect(isVehicleDisconnected({ last_updated: 5 })).toBe(false);
    });

    it('is true once telemetry is stale beyond the boundary', () => {
        expect(isVehicleDisconnected({ last_updated: 5.01 })).toBe(true);
    });
});

describe('vehicleStatus', () => {
    it('is "offline" when disconnected, regardless of selection', () => {
        expect(vehicleStatus(true, false)).toBe('offline');
        expect(vehicleStatus(true, true)).toBe('offline');
    });

    it('is "selected" when connected and selected', () => {
        expect(vehicleStatus(false, true)).toBe('selected');
    });

    it('is "online" when connected and not selected', () => {
        expect(vehicleStatus(false, false)).toBe('online');
    });
});

describe('vehicleStatusColor', () => {
    it('returns a distinct color per status', () => {
        const colors = ['offline', 'online', 'selected'].map(vehicleStatusColor);
        expect(new Set(colors).size).toBe(3);
    });

    it('uses the theme-adaptive secondary-text token for offline, not a raw (theme-invariant) gray', () => {
        // The app defaults to the dark PrimeReact theme, where raw --gray-*
        // tokens don't adapt and read as near-invisible against the dark
        // --surface-0 card background. --text-color-secondary does adapt.
        expect(vehicleStatusColor('offline')).toBe('var(--text-color-secondary)');
    });
});

describe('vehicleStatusMapColor', () => {
    it('returns a distinct color per status', () => {
        const colors = ['offline', 'online', 'selected'].map(vehicleStatusMapColor);
        expect(new Set(colors).size).toBe(3);
    });

    it('uses a different "online" shade than vehicleStatusColor, tuned for the dark map background', () => {
        expect(vehicleStatusMapColor('online')).not.toBe(vehicleStatusColor('online'));
    });
});

describe('vehicleStatusTextColor', () => {
    it('returns a distinct color per status', () => {
        const colors = ['offline', 'online', 'selected'].map(vehicleStatusTextColor);
        expect(new Set(colors).size).toBe(3);
    });

    it('uses white for the selected status, for contrast against its green marker', () => {
        expect(vehicleStatusTextColor('selected')).toBe('#ffffff');
    });
});

describe('sortVehiclesForDisplay', () => {
    const v = (name, last_updated) => ({ name, last_updated });

    it('puts selected vehicles before online, and online before offline', () => {
        const vehicles = [v('offline-1', 10), v('online-1', 0), v('selected-1', 0)];
        const result = sortVehiclesForDisplay(vehicles, ['selected-1']);
        expect(result.map((x) => x.name)).toEqual(['selected-1', 'online-1', 'offline-1']);
    });

    it('sorts alphabetically by name within the same status group', () => {
        const vehicles = [v('bravo', 0), v('alpha', 0), v('charlie', 0)];
        const result = sortVehiclesForDisplay(vehicles, []);
        expect(result.map((x) => x.name)).toEqual(['alpha', 'bravo', 'charlie']);
    });

    it('treats a null squadList as no selection', () => {
        const vehicles = [v('a', 0), v('b', 0)];
        const result = sortVehiclesForDisplay(vehicles, null);
        expect(result.map((x) => x.name)).toEqual(['a', 'b']);
    });

    it('does not mutate the input array', () => {
        const vehicles = [v('b', 0), v('a', 0)];
        sortVehiclesForDisplay(vehicles, []);
        expect(vehicles.map((x) => x.name)).toEqual(['b', 'a']);
    });
});
