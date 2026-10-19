import { describe, it, expect, afterEach, vi } from 'vitest';
import {
    createCatalogLoader, engineLocation, fetchCatalog, fetchDaemonCatalog, findVehicle,
    resolveNode, sameVehicle, shortType, vehicleKey, vehicleLabel, vehicleOptions,
} from './flowCatalog.js';
import { LAB_A, LAB_B, TYPES, catalogFixture, flowB } from './flowFixtures.js';

afterEach(() => {
    vi.unstubAllGlobals();
});

function stubFetch(impl) {
    vi.stubGlobal('window', { location: { protocol: 'http:', host: 'gcs:8000' } });
    const fetch = vi.fn(impl);
    vi.stubGlobal('fetch', fetch);
    return fetch;
}

const ok = (body) => async () => ({ status: 200, json: async () => body });

describe('fetchDaemonCatalog', () => {
    it('queries the catalog route for the daemon and returns its entries', async () => {
        const fetch = stubFetch(ok({ reachable: true, ok: true, vehicles: [{ name: 'harpy' }], engines: [] }));
        const result = await fetchDaemonCatalog(LAB_A);
        expect(fetch.mock.calls[0][0]).toBe('http://gcs:8000/api/flows/catalog?address=mock%3A%2F%2Flab-a');
        expect(result).toEqual({ ...LAB_A, reachable: true, error: null, vehicles: [{ name: 'harpy' }], engines: [] });
    });

    it('reports an unreachable daemon with its error', async () => {
        stubFetch(ok({ reachable: false, ok: false, error: 'connection refused' }));
        const result = await fetchDaemonCatalog(LAB_B);
        expect(result).toEqual({ ...LAB_B, reachable: false, error: 'connection refused', vehicles: [], engines: [] });
    });

    it('reports a network failure as unreachable', async () => {
        stubFetch(async () => { throw new Error('offline'); });
        const result = await fetchDaemonCatalog(LAB_A);
        expect(result.reachable).toBe(false);
        expect(result.error).toContain('offline');
    });
});

describe('fetchCatalog', () => {
    it('fetches every daemon in roster order', async () => {
        stubFetch(ok({ reachable: true, ok: true, vehicles: [], engines: [] }));
        const result = await fetchCatalog([LAB_A, LAB_B]);
        expect(result.map((d) => d.address)).toEqual([LAB_A.address, LAB_B.address]);
    });
});

describe('createCatalogLoader', () => {
    it('ignores a slower, older response that resolves after a newer one', async () => {
        const resolvers = [];
        vi.stubGlobal('window', { location: { protocol: 'http:', host: 'gcs:8000' } });
        vi.stubGlobal('fetch', vi.fn(() => new Promise((resolve) => resolvers.push(resolve))));
        const seen = [];
        const load = createCatalogLoader((c) => seen.push(c.map((d) => d.name)));
        const first = load([{ name: 'old', address: 'a' }]);
        const second = load([{ name: 'new', address: 'b' }]);
        const reply = { status: 200, json: async () => ({ reachable: true, ok: true, vehicles: [], engines: [] }) };
        resolvers[1](reply);
        await second;
        resolvers[0](reply);
        await first;
        expect(seen).toEqual([['new']]);
    });
});

describe('resolveNode', () => {
    const catalog = catalogFixture();
    const flow = flowB();

    it('resolves a producer to its stream type and camera details', () => {
        const r = resolveNode(flow, catalog, flow.nodes[1]);
        expect(r).toMatchObject({
            resolved: true, reason: null, output: TYPES.raw, accepts: [], events: [], eventTypes: {},
            category: null, typed: true, problem: null,
        });
        expect(r.stream).toMatchObject({ name: 'frames', kind: 'camera', primary: true, hres: 1080, vres: 720, fps: 30 });
    });

    it('resolves an engine to its accepts, event labels, event types and category', () => {
        expect(resolveNode(flow, catalog, flow.nodes[2])).toEqual({
            resolved: true, reason: null, output: null, stream: null,
            accepts: [TYPES.raw], events: ['result', 'dropped'],
            eventTypes: { result: TYPES.detection, dropped: TYPES.generic },
            category: 'detection', typed: true, problem: null, location: 'local',
        });
        expect(resolveNode(flow, catalog, flow.nodes[3]).location).toBe('remote');
    });

    it('passes an untyped entry\'s problem through', () => {
        const untyped = catalog.map((d) => ({
            ...d,
            engines: d.engines.map((e) => (e.name === 'yolo'
                ? { ...e, typed: false, problem: 'no plugin file', accepts: ['*'], events: [{ label: 'result', type: null }] }
                : e)),
        }));
        expect(resolveNode(flow, untyped, flow.nodes[2])).toMatchObject({
            typed: false, problem: 'no plugin file', events: ['result'], eventTypes: { result: null },
        });
    });

    it('gives unresolved nodes the same keys', () => {
        expect(resolveNode({ ...flow, vehicle: null }, catalog, flow.nodes[0])).toEqual({
            resolved: false, reason: 'no vehicle selected', output: null, stream: null, accepts: [], events: [],
            eventTypes: {}, category: null, typed: true, problem: null,
        });
    });

    it('explains why a node is unresolved', () => {
        const unreachable = catalog.map((d) => (d.address === LAB_B.address ? { ...d, reachable: false, vehicles: [], engines: [] } : d));
        expect(resolveNode(flow, unreachable, flow.nodes[3])).toMatchObject({ resolved: false, reason: 'daemon lab-b (mock) is unreachable' });
        expect(resolveNode(flow, [catalog[0]], flow.nodes[3]).reason).toBe('daemon lab-b (mock) is not in the roster');
        const gone = { ...flow.nodes[2], engine: 'tracker' };
        expect(resolveNode(flow, catalog, gone).reason).toBe('lab-a (mock) has no engine tracker');
        const noStream = { ...flow.nodes[0], stream: 'lidar' };
        expect(resolveNode(flow, catalog, noStream).reason).toBe('harpy has no stream lidar');
        expect(resolveNode({ ...flow, vehicle: null }, catalog, flow.nodes[0]).reason).toBe('no vehicle selected');
        const otherVehicle = { ...flow, vehicle: { name: 'osprey', daemon: { ...LAB_A } } };
        expect(resolveNode(otherVehicle, catalog, flow.nodes[0]).reason).toBe('lab-a (mock) has no vehicle osprey');
    });
});

describe('vehicles', () => {
    const catalog = catalogFixture();

    it('finds the bound vehicle', () => {
        expect(findVehicle(catalog, flowB().vehicle).name).toBe('harpy');
        expect(findVehicle(catalog, null)).toBeNull();
    });

    it('offers every vehicle on reachable daemons', () => {
        const options = vehicleOptions(catalog, null);
        expect(options.map((o) => vehicleLabel(o, options))).toEqual([
            'harpy @ lab-a (mock)', 'kestrel @ lab-a (mock)', 'harpy @ lab-b (mock)', 'kestrel @ lab-b (mock)',
        ]);
    });

    it('names a vehicle by its daemon only when another daemon has one of the same name', () => {
        const options = vehicleOptions([catalog[0]], null);
        expect(options.map((o) => vehicleLabel(o, options))).toEqual(['harpy', 'kestrel']);
        expect(vehicleLabel(flowB().vehicle)).toBe('harpy');
    });

    it('keeps the current binding as an option even when its daemon is unreachable', () => {
        const current = flowB().vehicle;
        const options = vehicleOptions([{ ...catalog[1] }], current);
        expect(options.some((o) => sameVehicle(o, current))).toBe(true);
    });

    it('keys vehicles by name and daemon address', () => {
        expect(vehicleKey(flowB().vehicle)).toBe('harpy@mock://lab-a');
    });

    it('derives engine location from the bound vehicle', () => {
        expect(engineLocation(flowB(), LAB_A.address)).toBe('local');
        expect(engineLocation(flowB(), LAB_B.address)).toBe('remote');
        expect(engineLocation({ ...flowB(), vehicle: null }, LAB_A.address)).toBe('remote');
    });
});

describe('shortType', () => {
    it('shortens protobuf type paths', () => {
        expect(shortType(TYPES.raw)).toBe('RawFrame');
        expect(shortType('*')).toBe('*');
        expect(shortType(null)).toBe('—');
        expect(shortType(undefined)).toBe('—');
    });
});
