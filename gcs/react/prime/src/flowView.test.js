import { describe, it, expect } from 'vitest';
import {
    CALLBACK_COLOR, CALLBACK_SPACING, ERROR_COLOR, NODE_COLOR, OUTPUT_COLOR, WARNING_COLOR,
    applyFlowEdgeChanges, applyFlowNodeChanges, connectionKind, legendEntries, mergeNodes, nodeBorderColor, paletteTitle, statusText, toReactFlow,
} from './flowView.js';
import { addEdge, validateFlow } from './flowModel.js';
import { TYPES, catalogFixture, flowB } from './flowFixtures.js';

const catalog = catalogFixture();
const clean = { errors: [], warnings: [] };

describe('toReactFlow', () => {
    it('maps nodes with labels, resolutions, and stream options', () => {
        const { nodes } = toReactFlow(flowB(), catalog, clean, { nodeId: 'p2' });
        expect(nodes.map((n) => [n.id, n.type, n.data.label, n.selected])).toEqual([
            ['p1', 'producer', 'harpy.telemetry', false],
            ['p2', 'producer', 'harpy.frames', true],
            ['e1', 'engine', 'yolo @ lab-a (mock)', false],
            ['e2', 'engine', 'telemetry @ lab-b (mock)', false],
        ]);
        expect(nodes[2].data.resolution.location).toBe('local');
        // each producer may switch only to itself or an unplaced stream
        expect(nodes[1].data.streamChoices.map((c) => c.name)).toEqual(['frames', 'thermal', 'downward']);
        expect(nodes[1].data.streamChoices[0]).toEqual({ name: 'frames', primary: true, disabled: false, reason: null });
        expect(nodes[2].data.streamChoices).toEqual([]);
        expect(nodes.map((n) => n.data.forwarded)).toEqual([null, null, [TYPES.raw], [TYPES.telemetry, TYPES.raw]]);
    });

    it('leaves resolutions null while the catalog loads', () => {
        const { nodes } = toReactFlow(flowB(), null, clean, null);
        expect(nodes.every((n) => n.data.resolution === null)).toBe(true);
        expect(nodes[1].data.streamChoices).toEqual([{ name: 'frames', primary: false, disabled: false, reason: null }]);
        expect(nodes.every((n) => n.data.forwarded === null)).toBe(true);
    });

    it('wires stream changes to the handler with the node id', () => {
        const calls = [];
        const { nodes } = toReactFlow(flowB(), catalog, clean, null, { onChangeStream: (...a) => calls.push(a) });
        nodes[0].data.onChangeStream('frames');
        expect(calls).toEqual([['p1', 'frames']]);
    });

    it('maps output and callback edges to their handles', () => {
        const flow = addEdge(flowB(), catalog, 'e1', 'p2', 'callback');
        const { edges } = toReactFlow(flow, catalog, clean, { edgeId: 'x4' });
        expect(edges[0]).toMatchObject({ id: 'x1', type: 'smoothstep', sourceHandle: 'out', targetHandle: 'in', label: '2s', selected: false });
        expect(edges[3]).toMatchObject({
            id: 'x4', type: 'callback', sourceHandle: 'cb', targetHandle: 'cb-in', selected: true,
            markerEnd: { type: 'arrowclosed', color: CALLBACK_COLOR },
        });
        const toEngine = toReactFlow(addEdge(flowB(), catalog, 'e1', 'e2', 'callback'), catalog, clean, null).edges[3];
        expect(toEngine.targetHandle).toBe('in');
    });

    it('spreads callbacks between the same two nodes apart', () => {
        const once = addEdge(flowB(), catalog, 'e1', 'p2', 'callback');
        const twice = addEdge(once, catalog, 'e1', 'p2', 'callback');
        const shifts = (flow) => toReactFlow(flow, catalog, clean, null).edges
            .filter((e) => e.type === 'callback').map((e) => [e.data.edge.event, e.data.shift]);
        expect(shifts(once)).toEqual([['result', 0]]);
        expect(shifts(twice)).toEqual([['result', -CALLBACK_SPACING / 2], ['dropped', CALLBACK_SPACING / 2]]);
        const outputs = toReactFlow(twice, catalog, clean, null).edges.filter((e) => e.type !== 'callback');
        expect(outputs.every((e) => e.data.shift === undefined)).toBe(true);
    });

    it('attaches validation issues to nodes and edges', () => {
        const validation = {
            errors: [{ nodeId: 'e1', message: 'bad node' }, { edgeId: 'x2', message: 'bad edge' }, { message: 'global' }],
            warnings: [{ nodeId: 'e1', message: 'hmm' }],
        };
        const { nodes, edges } = toReactFlow(flowB(), catalog, validation, null);
        expect(nodes[2].data.errors).toEqual(['bad node']);
        expect(nodes[2].data.warnings).toEqual(['hmm']);
        expect(edges[1].data.errors).toEqual(['bad edge']);
        expect(edges[1].style).toEqual({ stroke: ERROR_COLOR });
        expect(edges[0].style).toEqual({ stroke: OUTPUT_COLOR });
        expect(edges[0].markerEnd).toEqual({ type: 'arrowclosed', color: OUTPUT_COLOR });
        expect(edges[1].markerEnd).toEqual({ type: 'arrowclosed', color: ERROR_COLOR });
    });
});

describe('change application', () => {
    it('keeps React Flow measurements across re-derivation', () => {
        const prev = [{ id: 'p1', measured: { width: 10, height: 5 }, dragging: true, position: { x: 0, y: 0 } }];
        const next = [{ id: 'p1', position: { x: 3, y: 4 } }, { id: 'e1', position: { x: 0, y: 0 } }];
        expect(mergeNodes(prev, next)).toEqual([
            { id: 'p1', position: { x: 3, y: 4 }, measured: { width: 10, height: 5 }, dragging: true },
            { id: 'e1', position: { x: 0, y: 0 } },
        ]);
    });

    it('applies moves and removals to the flow', () => {
        let flow = applyFlowNodeChanges(flowB(), [
            { type: 'position', id: 'p1', position: { x: 9, y: 9 } },
            { type: 'position', id: 'p2' }, // drag end without a position
            { type: 'select', id: 'e1', selected: true },
        ]);
        expect(flow.nodes[0].position).toEqual({ x: 9, y: 9 });
        expect(flow.nodes[1].position).toEqual({ x: 0, y: 150 });
        flow = applyFlowNodeChanges(flow, [{ type: 'remove', id: 'e1' }]);
        expect(flow.nodes.map((n) => n.id)).toEqual(['p1', 'p2', 'e2']);
        flow = applyFlowEdgeChanges(flow, [{ type: 'remove', id: 'x1' }]);
        expect(flow.edges).toEqual([]);
    });

    it('returns the same flow object when nothing applies', () => {
        const flow = flowB();
        expect(applyFlowNodeChanges(flow, [{ type: 'dimensions', id: 'p1' }])).toBe(flow);
        expect(applyFlowEdgeChanges(flow, [{ type: 'select', id: 'x1' }])).toBe(flow);
    });
});

describe('display helpers', () => {
    it('uses a teal node accent distinct from the FSM builder', () => {
        expect(NODE_COLOR).not.toBe('#4a7a9b');
        expect(OUTPUT_COLOR).toBe(NODE_COLOR);
    });

    it('picks the connection kind from the handle', () => {
        expect(connectionKind('cb')).toBe('callback');
        expect(connectionKind('out')).toBe('output');
        expect(connectionKind(null)).toBe('output');
    });

    it('colors node borders by severity', () => {
        const base = { errors: [], warnings: [], resolution: { resolved: true } };
        expect(nodeBorderColor(base)).toBe(NODE_COLOR);
        expect(nodeBorderColor({ ...base, warnings: ['w'] })).toBe(WARNING_COLOR);
        expect(nodeBorderColor({ ...base, errors: ['e'] })).toBe(ERROR_COLOR);
        expect(nodeBorderColor({ ...base, resolution: { resolved: false } })).toBe(ERROR_COLOR);
    });

    it('describes a resolution', () => {
        expect(statusText(null)).toBe('loading…');
        expect(statusText({ resolved: false, reason: 'gone' })).toBe('unresolved: gone');
        expect(statusText({ resolved: true, output: 'image', typed: true })).toBe('out: image');
        expect(statusText({ resolved: true, output: 'image', typed: false })).toBe('out: image (untyped)');
        expect(statusText({ resolved: true, output: null, typed: true }, ['telemetry', 'image'])).toBe('fwd: telemetry, image');
        expect(statusText({ resolved: true, output: null, typed: false }, [])).toBe('fwd: — (untyped)');
    });

    it('shows short types in status lines', () => {
        const { nodes } = toReactFlow(flowB(), catalog, clean, null);
        const byId = Object.fromEntries(nodes.map((n) => [n.id, n.data]));
        expect(statusText(byId.p2.resolution)).toBe('out: RawFrame');
        expect(statusText(byId.e2.resolution, byId.e2.forwarded)).toBe('fwd: Telemetry, RawFrame');
        expect(statusText({ resolved: true, output: null, typed: true }, ['*'])).toBe('fwd: *');
    });

    it('builds palette tooltips', () => {
        const yolo = catalog[0].engines.find((e) => e.name === 'yolo');
        expect(paletteTitle(yolo)).toBe('accepts RawFrame · events: result, dropped');
        const untyped = { name: 'x', accepts: ['*'], events: [{ label: 'result', type: null }], typed: false, problem: 'no plugin file' };
        expect(paletteTitle(untyped)).toBe('accepts * · events: result · no plugin file');
    });

    it('is consistent with validateFlow output for Flow B', () => {
        const { nodes } = toReactFlow(flowB(), catalog, validateFlow(flowB(), catalog), null);
        expect(nodes.every((n) => nodeBorderColor(n.data) === NODE_COLOR)).toBe(true);
    });
});

describe('legendEntries', () => {
    const STAR = { symbol: '★', text: 'Primary camera: only one per flow, since primary cameras cannot stream at the same time' };

    it('explains the star when the bound vehicle has primary cameras', () => {
        expect(legendEntries(flowB(), catalog)).toEqual([STAR]);
    });

    it('is empty without a vehicle, a catalog, or any primary camera', () => {
        expect(legendEntries({ ...flowB(), vehicle: null }, catalog)).toEqual([]);
        expect(legendEntries(flowB(), null)).toEqual([]);
        const noPrimary = catalog.map((d) => ({ ...d, vehicles: d.vehicles.map((v) => ({ ...v, streams: v.streams.map((st) => ({ ...st, primary: false })) })) }));
        expect(legendEntries(flowB(), noPrimary)).toEqual([]);
    });
});
