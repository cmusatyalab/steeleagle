// Shared test fixtures for the Flow Builder modules: two mock daemons
// running the seed's vehicles and engines, and the reference "Flow B, early
// discard" flow from docs/superpowers/specs/2026-10-16-gcs-flow-builder-design.md.

export const LAB_A = { name: 'lab-a (mock)', address: 'mock://lab-a' };
export const LAB_B = { name: 'lab-b (mock)', address: 'mock://lab-b' };

const M = 'steeleagle_protocol/v1/messages';
export const TYPES = {
    telemetry: `${M}/telemetry/Telemetry`,
    raw: `${M}/frame/RawFrame`,
    encoded: `${M}/frame/EncodedFrame`,
    detection: `${M}/result/DetectionResult`,
    generic: `${M}/result/GenericResult`,
};

// Mirrors gcs/react/backend/app/mock_plugins/ in the catalog route's shape.
const TELEMETRY = { name: 'telemetry', kind: 'telemetry', type: TYPES.telemetry, primary: false, description: null, hres: null, vres: null, fps: null };
const camera = (name, type, primary, description, hres, vres, fps) => ({ name, kind: 'camera', type, primary, description, hres, vres, fps });

const HARPY_STREAMS = [
    TELEMETRY,
    camera('frames', TYPES.raw, true, 'Main RGB camera on gimbal', 1080, 720, 30),
    camera('thermal', TYPES.raw, true, 'Thermal camera on gimbal', 640, 512, 30),
    camera('downward', TYPES.encoded, false, 'Downward-facing navigation camera', 640, 480, 15),
];
const KESTREL_STREAMS = [TELEMETRY, camera('rgb', TYPES.raw, true, 'Main RGB camera on gimbal', 1080, 720, 30)];

const DETECTOR_EVENTS = [{ label: 'result', type: TYPES.detection }, { label: 'dropped', type: TYPES.generic }];
const ENGINES = [
    { name: 'detector', category: 'detection', accepts: [TYPES.raw], events: DETECTOR_EVENTS, typed: true, problem: null },
    { name: 'yolo', category: 'detection', accepts: [TYPES.raw], events: DETECTOR_EVENTS, typed: true, problem: null },
    { name: 'telemetry', category: 'generic', accepts: [TYPES.telemetry, TYPES.raw], events: [{ label: 'result', type: TYPES.generic }], typed: true, problem: null },
];

function daemonCatalog(daemon) {
    return {
        ...daemon,
        reachable: true,
        error: null,
        vehicles: [
            { name: 'harpy', streams: HARPY_STREAMS, typed: true, problem: null },
            { name: 'kestrel', streams: KESTREL_STREAMS, typed: true, problem: null },
        ],
        engines: ENGINES,
    };
}

export function catalogFixture() {
    return [daemonCatalog(LAB_A), daemonCatalog(LAB_B)];
}

export function flowB() {
    return {
        schemaVersion: 1,
        name: 'early-discard',
        vehicle: { name: 'harpy', daemon: { ...LAB_A } },
        nodes: [
            { id: 'p1', kind: 'producer', stream: 'telemetry', tokens: 1, position: { x: 0, y: 0 } },
            { id: 'p2', kind: 'producer', stream: 'frames', tokens: 1, position: { x: 0, y: 150 } },
            { id: 'e1', kind: 'engine', engine: 'yolo', daemon: { ...LAB_A }, position: { x: 250, y: 150 } },
            { id: 'e2', kind: 'engine', engine: 'telemetry', daemon: { ...LAB_B }, position: { x: 500, y: 0 } },
        ],
        edges: [
            { id: 'x1', kind: 'output', source: 'p1', target: 'e2', timeout: '2s' },
            { id: 'x2', kind: 'output', source: 'p2', target: 'e1', timeout: '1s' },
            { id: 'x3', kind: 'output', source: 'e1', target: 'e2', timeout: '2s' },
        ],
    };
}
