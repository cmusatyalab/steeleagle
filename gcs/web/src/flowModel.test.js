import { describe, it, expect } from 'vitest';
import {
    addEngine, addProducer, availableStreams, emptyFlow, exportName, fileBaseName, isEnginePlaced,
    nodeLabel, parseFlowJson, removeEdge, removeNode, serializeFlow, setVehicle, updateEdge, updateNode,
    acceptsAll, addEdge, canConnect, forwardedTypes, streamChoices, toGabrielToml, validateFlow,
} from './flowModel.js';
import { LAB_A, LAB_B, TYPES, catalogFixture, flowB } from './flowFixtures.js';

const AT = { x: 1, y: 2 };

describe('document operations', () => {
    it('starts empty with no vehicle', () => {
        expect(emptyFlow()).toEqual({ schemaVersion: 1, name: 'untitled-flow', vehicle: null, nodes: [], edges: [] });
    });

    it('adds producers with default tokens and refuses duplicates or no vehicle', () => {
        const flow = setVehicle(emptyFlow(), flowB().vehicle);
        const next = addProducer(flow, 'frames', AT);
        expect(next.nodes).toEqual([{ id: 'p1', kind: 'producer', stream: 'frames', tokens: 1, position: AT }]);
        expect(() => addProducer(next, 'frames', AT)).toThrow('harpy.frames is already on the canvas');
        expect(() => addProducer(emptyFlow(), 'frames', AT)).toThrow('Select a vehicle first');
    });

    it('adds each engine at most once per daemon', () => {
        const once = addEngine(emptyFlow(), LAB_A, 'yolo', AT);
        expect(once.nodes[0]).toEqual({ id: 'e1', kind: 'engine', engine: 'yolo', daemon: { ...LAB_A }, position: AT });
        expect(() => addEngine(once, LAB_A, 'yolo', AT)).toThrow('yolo @ lab-a (mock) is already on the canvas');
        expect(addEngine(once, LAB_B, 'yolo', AT).nodes).toHaveLength(2);
        expect(isEnginePlaced(once, LAB_A.address, 'yolo')).toBe(true);
        expect(isEnginePlaced(once, LAB_B.address, 'yolo')).toBe(false);
    });

    it('allocates ids past the highest existing one', () => {
        const flow = addEngine(flowB(), LAB_B, 'yolo', AT);
        expect(flow.nodes.at(-1).id).toBe('e3');
    });

    it('lists the bound vehicle streams not yet placed', () => {
        const flow = { ...flowB(), nodes: flowB().nodes.filter((n) => n.stream !== 'frames') };
        expect(availableStreams(flow, catalogFixture())).toEqual(['frames', 'thermal', 'downward']);
        expect(availableStreams(flowB(), catalogFixture())).toEqual(['downward']);
        expect(availableStreams(emptyFlow(), catalogFixture())).toEqual([]);
    });

    it('updates and removes nodes and edges', () => {
        const flow = flowB();
        expect(updateNode(flow, 'p1', { tokens: 3 }).nodes[0].tokens).toBe(3);
        expect(updateEdge(flow, 'x1', { timeout: '5s' }).edges[0].timeout).toBe('5s');
        const withoutYolo = removeNode(flow, 'e1');
        expect(withoutYolo.nodes.map((n) => n.id)).toEqual(['p1', 'p2', 'e2']);
        expect(withoutYolo.edges.map((e) => e.id)).toEqual(['x1']);
        expect(removeEdge(flow, 'x2').edges.map((e) => e.id)).toEqual(['x1', 'x3']);
    });

    it('drops producers and their edges when the vehicle changes, keeping engines', () => {
        const flow = setVehicle(flowB(), { name: 'kestrel', daemon: { ...LAB_A } });
        expect(flow.vehicle.name).toBe('kestrel');
        expect(flow.nodes.map((n) => n.id)).toEqual(['e1', 'e2']);
        expect(flow.edges.map((e) => e.id)).toEqual(['x3']);
    });

    it('keeps producers when the same vehicle is set again', () => {
        const flow = setVehicle(flowB(), { name: 'harpy', daemon: { ...LAB_A } });
        expect(flow.nodes).toHaveLength(4);
    });

    it('labels nodes and names them for Gabriel', () => {
        const flow = flowB();
        expect(nodeLabel(flow, flow.nodes[1])).toBe('harpy.frames');
        expect(nodeLabel(flow, flow.nodes[2])).toBe('yolo @ lab-a (mock)');
        expect(flow.nodes.map((n) => exportName(flow, n))).toEqual(['harpy.telemetry', 'harpy.frames', 'harpy.yolo', 'telemetry']);
    });

    it('derives a safe export file name', () => {
        expect(fileBaseName(flowB())).toBe('early-discard');
        expect(fileBaseName({ ...flowB(), name: 'Early discard / v2' })).toBe('Early-discard-v2');
        expect(fileBaseName({ ...flowB(), name: '  ' })).toBe('flow');
    });
});

describe('JSON import/export', () => {
    it('round-trips a flow', () => {
        expect(parseFlowJson(serializeFlow(flowB()))).toEqual(flowB());
    });

    it('fills in missing tokens and timeouts with defaults', () => {
        const doc = flowB();
        delete doc.nodes[0].tokens;
        delete doc.edges[0].timeout;
        const flow = parseFlowJson(JSON.stringify(doc));
        expect(flow.nodes[0].tokens).toBe(1);
        expect(flow.edges[0].timeout).toBe('1s');
    });

    it.each([
        ['{not json', /not valid JSON/],
        ['[]', 'not a flow document'],
        [JSON.stringify({ ...flowB(), schemaVersion: 2 }), 'unsupported schemaVersion 2 (expected 1)'],
        [JSON.stringify({ ...flowB(), name: 7 }), 'name must be a string'],
        [JSON.stringify({ ...flowB(), vehicle: { name: 'harpy' } }), 'vehicle must be null or {name, daemon: {name, address}}'],
        [JSON.stringify({ ...flowB(), nodes: {} }), 'nodes and edges must be arrays'],
        [JSON.stringify({ ...flowB(), nodes: [...flowB().nodes, flowB().nodes[0]] }), 'duplicate node id p1'],
        [JSON.stringify({ ...flowB(), nodes: [{ ...flowB().nodes[0], kind: 'sink' }], edges: [] }), 'node p1: unknown kind "sink"'],
        [JSON.stringify({ ...flowB(), nodes: [{ ...flowB().nodes[2], daemon: 'lab-a' }], edges: [] }), 'node e1: engine nodes need an engine name and daemon {name, address}'],
        [JSON.stringify({ ...flowB(), nodes: [{ ...flowB().nodes[0], position: null }], edges: [] }), 'node p1: position must be {x, y}'],
        [JSON.stringify({ ...flowB(), edges: [{ ...flowB().edges[0], target: 'zz' }] }), 'edge x1 references a missing node'],
        [JSON.stringify({ ...flowB(), edges: [...flowB().edges, flowB().edges[0]] }), 'duplicate edge id x1'],
        [JSON.stringify({ ...flowB(), edges: [{ id: 'x9', kind: 'callback', source: 'e1', target: 'p2' }] }), 'edge x9: callback edges need an event'],
        [JSON.stringify({ ...flowB(), edges: [{ id: 'x9', kind: 'magic', source: 'e1', target: 'p2' }] }), 'edge x9: unknown kind "magic"'],
    ])('rejects %s', (text, message) => {
        expect(() => parseFlowJson(text)).toThrow(message);
    });
});

describe('acceptsAll', () => {
    it('requires every type to be accepted, with * accepting anything', () => {
        expect(acceptsAll(['image'], ['image'])).toBe(true);
        expect(acceptsAll(['image'], ['image', 'telemetry'])).toBe(false);
        expect(acceptsAll(['telemetry', 'image'], ['image', 'telemetry'])).toBe(true);
        expect(acceptsAll(['*'], ['telemetry'])).toBe(true);
        expect(acceptsAll(['image'], [])).toBe(true);
    });
});

describe('forwardedTypes', () => {
    const catalog = catalogFixture();

    it('collects producer inputs and the engine parent, in order', () => {
        expect(forwardedTypes(flowB(), catalog, 'e1')).toEqual([TYPES.raw]);
        expect(forwardedTypes(flowB(), catalog, 'e2')).toEqual([TYPES.telemetry, TYPES.raw]);
    });

    it('is empty for an engine with no inputs', () => {
        expect(forwardedTypes({ ...flowB(), edges: [] }, catalog, 'e1')).toEqual([]);
    });

    it('terminates on a cycle in an imported flow', () => {
        const flow = { ...flowB(), edges: [...flowB().edges, { id: 'x9', kind: 'output', source: 'e2', target: 'e1', timeout: '1s' }] };
        expect(forwardedTypes(flow, catalog, 'e1')).toEqual([TYPES.raw, TYPES.telemetry]);
    });
});

describe('output edges', () => {
    const catalog = catalogFixture();
    // Flow B without edges, plus detector on lab-a as a second engine.
    const bare = () => addEngine({ ...flowB(), edges: [] }, LAB_A, 'detector', AT); // detector = e3

    it('builds Flow B edge by edge', () => {
        let flow = bare();
        flow = addEdge(flow, catalog, 'p1', 'e2', 'output');
        flow = addEdge(flow, catalog, 'p2', 'e1', 'output');
        flow = addEdge(flow, catalog, 'e1', 'e2', 'output');
        expect(flow.edges).toEqual([
            { id: 'x1', kind: 'output', source: 'p1', target: 'e2', timeout: '1s' },
            { id: 'x2', kind: 'output', source: 'p2', target: 'e1', timeout: '1s' },
            { id: 'x3', kind: 'output', source: 'e1', target: 'e2', timeout: '1s' },
        ]);
    });

    it('only ends at engines', () => {
        expect(canConnect(bare(), catalog, 'e1', 'p1', 'output')).toBe('output edges must end at an engine');
    });

    it('checks types', () => {
        expect(canConnect(bare(), catalog, 'p1', 'e1', 'output')).toBe('yolo @ lab-a (mock) does not accept Telemetry');
    });

    it('allows many producer inputs but only one engine input', () => {
        const flow = addEdge(addEdge(bare(), catalog, 'p1', 'e2', 'output'), catalog, 'e1', 'e2', 'output');
        // detector forwards nothing yet, so only the engine-input rule refuses
        expect(canConnect(flow, catalog, 'e3', 'e2', 'output')).toBe('telemetry @ lab-b (mock) already has an engine input');
        // a second producer input is still fine
        const twoCams = addEdge(bare(), catalog, 'p2', 'e1', 'output');
        expect(canConnect(twoCams, catalog, 'p2', 'e3', 'output')).toBeNull();
    });

    it('refuses duplicates, self-loops, and cycles', () => {
        const flow = addEdge(bare(), catalog, 'p2', 'e1', 'output');
        expect(canConnect(flow, catalog, 'p2', 'e1', 'output')).toBe('these nodes are already connected');
        expect(canConnect(flow, catalog, 'e1', 'e1', 'output')).toBe('an engine cannot feed itself');
        // e1 -> e3 is fine; then e3 -> e1 would close a loop. Use wildcard
        // engines so types don't get in the way.
        const wild = catalog.map((d) => ({ ...d, engines: d.engines.map((e) => ({ ...e, accepts: ['*'] })) }));
        const chain = addEdge(bare(), wild, 'e1', 'e3', 'output');
        expect(canConnect(chain, wild, 'e3', 'e1', 'output')).toBe('this would create a cycle');
    });

    it('refuses unresolved nodes', () => {
        const flow = addEngine(bare(), LAB_A, 'tracker', AT); // e4, not in the catalog
        expect(canConnect(flow, catalog, 'p2', 'e4', 'output')).toBe('cannot connect an unresolved node');
    });

    it('throws from addEdge when refused', () => {
        expect(() => addEdge(bare(), catalog, 'p1', 'e1', 'output')).toThrow('does not accept Telemetry');
    });

    it('refuses an engine edge unless every forwarded type is accepted', () => {
        // telemetry (e2) takes both streams, then forwards telemetry + image;
        // detector (e3) accepts image only.
        let flow = addEdge(bare(), catalog, 'p1', 'e2', 'output');
        flow = addEdge(flow, catalog, 'p2', 'e2', 'output');
        expect(canConnect(flow, catalog, 'e2', 'e3', 'output')).toBe('detector @ lab-a (mock) does not accept Telemetry');
        // yolo forwards image only, which detector accepts
        const yoloChain = addEdge(bare(), catalog, 'p2', 'e1', 'output');
        expect(canConnect(yoloChain, catalog, 'e1', 'e3', 'output')).toBeNull();
    });

    it('lets an engine with no inputs connect onward (nothing forwarded yet)', () => {
        expect(canConnect(bare(), catalog, 'e2', 'e3', 'output')).toBeNull();
    });

    it('downstream re-check: refuses an input that would push an unaccepted type down the chain', () => {
        let flow = addEdge(bare(), catalog, 'p2', 'e2', 'output'); // e2 forwards image
        flow = addEdge(flow, catalog, 'e2', 'e3', 'output');       // detector accepts image
        expect(canConnect(flow, catalog, 'p1', 'e2', 'output'))
            .toBe('this would forward Telemetry to detector @ lab-a (mock), which does not accept it');
        expect(() => addEdge(flow, catalog, 'p1', 'e2', 'output')).toThrow('which does not accept it');
    });

    it('downstream re-check only blames types the new edge introduces', () => {
        // Stale/imported: e2 already forwards telemetry to image-only detector.
        const stale = { ...bare(), edges: [
            { id: 'x1', kind: 'output', source: 'p1', target: 'e2', timeout: '1s' },
            { id: 'x2', kind: 'output', source: 'e2', target: 'e3', timeout: '1s' },
        ] };
        // Adding frames only adds image, which detector accepts: allowed
        // (the existing x2 problem stays flagged by validateFlow).
        expect(canConnect(stale, catalog, 'p2', 'e2', 'output')).toBeNull();
    });
});

describe('callback edges', () => {
    const catalog = catalogFixture();

    it('picks the first event not yet used toward that target', () => {
        let flow = addEdge(flowB(), catalog, 'e1', 'p2', 'callback');
        flow = addEdge(flow, catalog, 'e1', 'p2', 'callback');
        expect(flow.edges.slice(-2)).toEqual([
            { id: 'x4', kind: 'callback', source: 'e1', target: 'p2', event: 'result' },
            { id: 'x5', kind: 'callback', source: 'e1', target: 'p2', event: 'dropped' },
        ]);
        expect(canConnect(flow, catalog, 'e1', 'p2', 'callback')).toBe('every event of yolo @ lab-a (mock) already has a callback to harpy.frames');
    });

    it('may target any other node', () => {
        expect(canConnect(flowB(), catalog, 'e1', 'e2', 'callback')).toBeNull();
        expect(canConnect(flowB(), catalog, 'e1', 'p1', 'callback')).toBeNull();
    });

    it('must start at an engine that declares events', () => {
        expect(canConnect(flowB(), catalog, 'p2', 'e1', 'callback')).toBe('callbacks must start at an engine');
        // Every plugin-file engine emits result; an odd catalog entry may not.
        const silent = catalog.map((d) => ({ ...d, engines: d.engines.map((e) => (e.name === 'telemetry' ? { ...e, events: [] } : e)) }));
        expect(canConnect(flowB(), silent, 'e2', 'p1', 'callback')).toBe('telemetry @ lab-b (mock) declares no events');
        expect(canConnect(flowB(), catalog, 'e1', 'e1', 'callback')).toBe('a callback cannot target its own engine');
    });
});

describe('primary cameras', () => {
    const catalog = catalogFixture();
    const harpy = () => ({ ...emptyFlow(), vehicle: { name: 'harpy', daemon: { ...LAB_A } } });
    const choice = (choices, name) => choices.find((c) => c.name === name);

    it('offers primary cameras until one is placed', () => {
        expect(availableStreams(harpy(), catalog)).toEqual(['telemetry', 'frames', 'thermal', 'downward']);
        expect(availableStreams(addProducer(harpy(), 'frames', AT), catalog)).toEqual(['telemetry', 'downward']);
    });

    it('marks the blocked primary camera with a reason', () => {
        const flow = addProducer(harpy(), 'frames', AT);
        expect(choice(streamChoices(flow, catalog), 'thermal')).toEqual({
            name: 'thermal', primary: true, disabled: true, reason: 'harpy.frames is already streaming a primary camera',
        });
        expect(choice(streamChoices(flow, catalog), 'downward')).toEqual({ name: 'downward', primary: false, disabled: false, reason: null });
    });

    it('lets the primary producer switch to another primary camera', () => {
        let flow = addProducer(harpy(), 'frames', AT);     // p1
        flow = addProducer(flow, 'telemetry', AT);         // p2
        expect(choice(streamChoices(flow, catalog, 'p1'), 'thermal')).toMatchObject({ disabled: false, reason: null });
        expect(choice(streamChoices(flow, catalog, 'p1'), 'frames')).toMatchObject({ primary: true, disabled: false });
        expect(choice(streamChoices(flow, catalog, 'p2'), 'thermal')).toMatchObject({ disabled: true });
    });

    it('keeps a producer\'s own stream even when the catalog lacks it', () => {
        const flow = addProducer(harpy(), 'lidar', AT);
        expect(choice(streamChoices(flow, catalog, 'p1'), 'lidar')).toEqual({ name: 'lidar', primary: false, disabled: false, reason: null });
    });

    it('reports two primary producers in an imported flow', () => {
        const flow = { ...harpy(), nodes: [
            { id: 'p1', kind: 'producer', stream: 'frames', tokens: 1, position: AT },
            { id: 'p2', kind: 'producer', stream: 'thermal', tokens: 1, position: AT },
        ] };
        const primaryErrors = validateFlow(flow, catalog).errors.filter((e) => e.message.includes('both primary cameras'));
        expect(primaryErrors).toEqual([
            { nodeId: 'p2', message: 'harpy.thermal and harpy.frames are both primary cameras; only one can stream at a time' },
        ]);
    });
});

describe('catalog problems', () => {
    const withProblems = (vehicleProblem, engineChange) => catalogFixture().map((d) => ({
        ...d,
        vehicles: d.vehicles.map((v) => (v.name === 'harpy' ? { ...v, problem: vehicleProblem } : v)),
        engines: d.engines.map((e) => (e.name === 'yolo' ? { ...e, ...engineChange } : e)),
    }));
    const messages = (flow, catalog) => validateFlow(flow, catalog).warnings.map((w) => w.message);

    it('warns about the bound vehicle\'s problem once, even with no producers', () => {
        const catalog = withProblems('camera "rgb" has no type; skipped', {});
        const flow = { ...emptyFlow(), vehicle: { name: 'harpy', daemon: { ...LAB_A } } };
        expect(messages(flow, catalog)).toEqual(['harpy: camera "rgb" has no type; skipped']);
        expect(messages(flowB(), catalog).filter((m) => m.startsWith('harpy:'))).toHaveLength(1);
    });

    it('says why an engine is untyped', () => {
        const catalog = withProblems(null, { typed: false, problem: 'no plugin file', accepts: ['*'], events: [{ label: 'result', type: null }] });
        expect(messages(flowB(), catalog)).toContain('yolo @ lab-a (mock): no type information (no plugin file); connections are not type-checked');
    });

    it('reports a typed engine\'s dropped entries', () => {
        const catalog = withProblems(null, { problem: 'an event has no label; skipped' });
        expect(messages(flowB(), catalog)).toContain('yolo @ lab-a (mock): an event has no label; skipped');
    });
});

describe('result events', () => {
    const catalog = catalogFixture();

    it('defaults a new callback to result', () => {
        let flow = addEdge(flowB(), catalog, 'e1', 'p2', 'callback');
        expect(flow.edges.at(-1).event).toBe('result');
        flow = addEdge(flow, catalog, 'e1', 'p2', 'callback');
        expect(flow.edges.at(-1).event).toBe('dropped');
    });

    it('flags an old flow\'s detections callback', () => {
        const flow = { ...flowB(), edges: [...flowB().edges, { id: 'x4', kind: 'callback', source: 'e1', target: 'p2', event: 'detections' }] };
        expect(validateFlow(flow, catalog).errors.map((e) => e.message).join(' | ')).toContain('does not emit detections');
    });
});

describe('validateFlow', () => {
    const catalog = catalogFixture();
    const messages = (issues) => issues.map((i) => i.message);

    it('passes Flow B cleanly', () => {
        expect(validateFlow(flowB(), catalog)).toEqual({ errors: [], warnings: [] });
    });

    it('reports a local engine whose export name collides with a producer', () => {
        const cat = catalogFixture().map((d) => (d.address === LAB_A.address
            ? { ...d, engines: [...d.engines, { name: 'frames', accepts: ['*'], events: [], typed: false }] }
            : d));
        const flow = addEngine(flowB(), LAB_A, 'frames', AT);
        expect(messages(validateFlow(flow, cat).errors).some((m) => m.includes('would both be named "harpy.frames" in Gabriel TOML'))).toBe(true);
    });

    it('catches a second engine input on an imported flow', () => {
        const base = addEngine(flowB(), LAB_A, 'detector', AT);
        const flow = { ...base, edges: [...base.edges, { id: 'x9', kind: 'output', source: 'e3', target: 'e2', timeout: '1s' }] };
        const { errors } = validateFlow(flow, catalog);
        expect(errors.some((e) => ['x9', 'x3'].includes(e.edgeId) && e.message.endsWith('already has an engine input'))).toBe(true);
    });

    it('requires a vehicle', () => {
        expect(messages(validateFlow(emptyFlow(), catalog).errors)).toEqual(['No vehicle selected']);
    });

    it('reports unresolved nodes against the node', () => {
        const offline = catalog.map((d) => (d.address === LAB_B.address ? { ...d, reachable: false, vehicles: [], engines: [] } : d));
        const { errors } = validateFlow(flowB(), offline);
        expect(errors).toContainEqual({ nodeId: 'e2', message: 'telemetry @ lab-b (mock): daemon lab-b (mock) is unreachable' });
        // edges touching an unresolved node aren't double-reported
        expect(errors.filter((e) => e.edgeId)).toEqual([]);
    });

    it('reports edges broken by a catalog change', () => {
        const changed = catalog.map((d) => ({
            ...d,
            engines: d.engines.map((e) => (e.name === 'yolo' ? { ...e, accepts: ['lidar'] } : e)),
        }));
        expect(validateFlow(flowB(), changed).errors).toEqual([
            { edgeId: 'x2', message: 'harpy.frames → yolo @ lab-a (mock): yolo @ lab-a (mock) does not accept RawFrame' },
        ]);
    });

    it('reports a second engine input and a cycle from an imported file', () => {
        const wild = catalog.map((d) => ({ ...d, engines: d.engines.map((e) => ({ ...e, accepts: ['*'] })) }));
        const flow = {
            ...flowB(),
            edges: [
                ...flowB().edges,
                { id: 'x4', kind: 'output', source: 'e2', target: 'e1', timeout: '1s' },
            ],
        };
        const msgs = messages(validateFlow(flow, wild).errors);
        expect(msgs.some((m) => m.endsWith('this would create a cycle'))).toBe(true);
    });

    it('checks timeout format and tokens', () => {
        let flow = updateEdge(flowB(), 'x1', { timeout: '2 seconds' });
        flow = updateEdge(flow, 'x2', { timeout: '' });
        flow = updateNode(flow, 'p1', { tokens: 0 });
        expect(messages(validateFlow(flow, catalog).errors)).toEqual([
            'harpy.telemetry: tokens must be a whole number of at least 1',
            'harpy.telemetry → telemetry @ lab-b (mock): timeout "2 seconds" is not a duration like 500ms, 1s, or 2m',
            'harpy.frames → yolo @ lab-a (mock): timeout "" is not a duration like 500ms, 1s, or 2m',
        ]);
        for (const ok of ['500ms', '1s', '1.5s', '2m']) {
            expect(validateFlow(updateEdge(flowB(), 'x1', { timeout: ok }), catalog).errors).toEqual([]);
        }
    });

    it('checks callback events against the catalog', () => {
        const flow = { ...flowB(), edges: [...flowB().edges, { id: 'x4', kind: 'callback', source: 'e1', target: 'p2', event: 'exploded' }] };
        expect(messages(validateFlow(flow, catalog).errors)).toEqual([
            'yolo @ lab-a (mock) → harpy.frames: yolo @ lab-a (mock) does not emit exploded',
        ]);
    });

    it('reports nodes placed twice by an imported file', () => {
        const flow = { ...flowB(), nodes: [...flowB().nodes, { ...flowB().nodes[2], id: 'e9' }] };
        expect(validateFlow(flow, catalog).errors).toContainEqual({ nodeId: 'e9', message: 'yolo @ lab-a (mock) appears more than once' });
    });

    it('reports export-name collisions', () => {
        // a remote telemetry engine on a third daemon also exports as "telemetry"
        const labC = { name: 'lab-c', address: 'mock://lab-c' };
        const withC = [...catalog, { ...catalog[1], ...labC }];
        const flow = addEngine(flowB(), labC, 'telemetry', AT);
        expect(messages(validateFlow(flow, withC).errors)).toContain(
            'telemetry @ lab-b (mock) and telemetry @ lab-c would both be named "telemetry" in Gabriel TOML',
        );
    });

    it('reports a forwarded type the downstream engine does not accept, once, on that edge', () => {
        const base = addEngine(flowB(), LAB_A, 'detector', AT); // e3
        const flow = {
            ...base,
            edges: [
                { id: 'x1', kind: 'output', source: 'p1', target: 'e2', timeout: '1s' },
                { id: 'x2', kind: 'output', source: 'p2', target: 'e2', timeout: '1s' },
                { id: 'x3', kind: 'output', source: 'e2', target: 'e3', timeout: '1s' },
            ],
        };
        expect(validateFlow(flow, catalog).errors).toEqual([
            { edgeId: 'x3', message: 'telemetry @ lab-b (mock) → detector @ lab-a (mock): detector @ lab-a (mock) does not accept Telemetry' },
        ]);
    });

    it('warns about engines with no input and untyped nodes', () => {
        const untyped = catalog.map((d) => ({ ...d, engines: [...d.engines, { name: 'tracker', accepts: ['*'], events: [], typed: false }] }));
        const flow = addEngine(flowB(), LAB_A, 'tracker', AT);
        expect(validateFlow(flow, untyped).warnings).toEqual([
            { nodeId: 'e3', message: 'tracker @ lab-a (mock): no type information; connections are not type-checked' },
            { nodeId: 'e3', message: 'Nothing feeds into tracker @ lab-a (mock)' },
        ]);
    });
});

// The flow run against the new Gabriel on 2026-10-15, with {vehicle} = harpy
// (comments removed). The export must reproduce it exactly.
const FLOW_B_TOML = `[[gabriel.flow.producers]]
name = "harpy.telemetry"
[[gabriel.flow.producers]]
name = "harpy.frames"

[[gabriel.flow.engines]]
name = "harpy.yolo"
location = "local"
[[gabriel.flow.engines]]
name = "telemetry"
location = "remote"

[[gabriel.flow.edges]]
from = "harpy.telemetry"
to = "telemetry"
timeout = "2s"
[[gabriel.flow.edges]]
from = "harpy.frames"
to = "harpy.yolo"
timeout = "1s"
[[gabriel.flow.edges]]
from = "harpy.yolo"
to = "telemetry"
timeout = "2s"
`;

describe('toGabrielToml', () => {
    const catalog = catalogFixture();

    it('reproduces the reference Flow B', () => {
        expect(toGabrielToml(flowB(), catalog)).toBe(FLOW_B_TOML);
    });

    it('emits tokens only when not the default', () => {
        const toml = toGabrielToml(updateNode(flowB(), 'p2', { tokens: 3 }), catalog);
        expect(toml).toContain('[[gabriel.flow.producers]]\nname = "harpy.frames"\ntokens = 3\n');
        expect(toml.match(/tokens/g)).toHaveLength(1);
    });

    it('omits callbacks with a header comment', () => {
        const flow = addEdge(flowB(), catalog, 'e1', 'p2', 'callback');
        const toml = toGabrielToml(flow, catalog);
        expect(toml).toBe('# 1 callback edge(s) omitted: Gabriel flow TOML has no callback representation yet.\n\n' + FLOW_B_TOML);
    });

    it('refuses a flow with errors', () => {
        expect(() => toGabrielToml(emptyFlow(), catalog)).toThrow('flow has 1 error(s); fix them before exporting TOML');
    });

    it('escapes names safely', () => {
        const quoted = catalog.map((d) => ({
            ...d,
            vehicles: d.vehicles.map((v) => ({ ...v, streams: [...v.streams, { name: 'cam"1', output: 'image' }] })),
        }));
        const flow = addProducer(flowB(), 'cam"1', AT);
        expect(toGabrielToml(flow, quoted)).toContain('name = "harpy.cam\\"1"');
    });
});
