// Maps a flow document (flowModel.js) to React Flow nodes and edges and
// back, for FlowBuilder.jsx. The flow document is the source of truth:
// React Flow state is re-derived from it, carrying over only what React
// Flow measures itself (node sizes, drag state). Kept free of React and
// @xyflow imports so it runs under vitest's node environment.
import { findVehicle, resolveNode, shortType } from './flowCatalog.js';
import { forwardedTypes, nodeLabel, removeEdge, removeNode, streamChoices, updateNode } from './flowModel.js';

export const ERROR_COLOR = '#ff4444';
export const WARNING_COLOR = '#e8c87a';
// Teal, so the Flow Builder reads differently from the FSM builder's blue.
export const NODE_COLOR = '#2a9d8f';
export const OUTPUT_COLOR = NODE_COLOR;
export const CALLBACK_COLOR = '#c47aff';
// Pixels between callbacks that share a source and target, so each event's
// edge and label stay visible instead of drawing over one another.
export const CALLBACK_SPACING = 16;
export const SELECTED_COLOR = '#7ecfff';

// dataTransfer type for palette items dragged onto the canvas; the payload
// is JSON: {kind: 'vehicle'} or {kind: 'engine', daemon: {name, address}, engine}.
export const FLOW_DRAG_TYPE = 'application/steeleagle-flow';

function messagesBy(issues, key) {
    const map = new Map();
    for (const issue of issues) {
        if (issue[key]) map.set(issue[key], [...(map.get(issue[key]) ?? []), issue.message]);
    }
    return map;
}

// A producer may switch to its own stream or any stream no other producer
// uses (flowModel.streamChoices). While the catalog loads, only its own
// stream is offered.
function producerChoices(flow, catalog, node) {
    return catalog
        ? streamChoices(flow, catalog, node.id)
        : [{ name: node.stream, primary: false, disabled: false, reason: null }];
}

export function toReactFlow(flow, catalog, validation, selection, handlers = {}) {
    const nodeErrors = messagesBy(validation.errors, 'nodeId');
    const nodeWarnings = messagesBy(validation.warnings, 'nodeId');
    const edgeErrors = messagesBy(validation.errors, 'edgeId');
    const byId = new Map(flow.nodes.map((n) => [n.id, n]));

    const nodes = flow.nodes.map((node) => {
        const isProducer = node.kind === 'producer';
        return {
            id: node.id,
            type: isProducer ? 'producer' : 'engine',
            position: node.position,
            selected: selection?.nodeId === node.id,
            data: {
                node,
                label: nodeLabel(flow, node),
                resolution: catalog ? resolveNode(flow, catalog, node) : null,
                forwarded: !isProducer && catalog ? forwardedTypes(flow, catalog, node.id) : null,
                errors: nodeErrors.get(node.id) ?? [],
                warnings: nodeWarnings.get(node.id) ?? [],
                streamChoices: isProducer ? producerChoices(flow, catalog, node) : [],
                ...(isProducer && handlers.onChangeStream
                    ? { onChangeStream: (stream) => handlers.onChangeStream(node.id, stream) }
                    : {}),
            },
        };
    });

    const siblings = new Map();
    for (const edge of flow.edges) {
        if (edge.kind !== 'callback') continue;
        const key = `${edge.source}->${edge.target}`;
        siblings.set(key, [...(siblings.get(key) ?? []), edge.id]);
    }
    const shiftOf = (edge) => {
        const ids = siblings.get(`${edge.source}->${edge.target}`);
        return (ids.indexOf(edge.id) - (ids.length - 1) / 2) * CALLBACK_SPACING;
    };

    const edges = flow.edges.map((edge) => {
        const errors = edgeErrors.get(edge.id) ?? [];
        const common = {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            selected: selection?.edgeId === edge.id,
            data: { edge, errors },
        };
        if (edge.kind === 'callback') {
            return {
                ...common,
                data: { ...common.data, shift: shiftOf(edge) },
                type: 'callback',
                sourceHandle: 'cb',
                targetHandle: byId.get(edge.target)?.kind === 'producer' ? 'cb-in' : 'in',
                markerEnd: { type: 'arrowclosed', color: errors.length ? ERROR_COLOR : CALLBACK_COLOR },
            };
        }
        return {
            ...common,
            type: 'smoothstep',
            sourceHandle: 'out',
            targetHandle: 'in',
            label: edge.timeout,
            markerEnd: { type: 'arrowclosed', color: errors.length ? ERROR_COLOR : OUTPUT_COLOR },
            style: { stroke: errors.length ? ERROR_COLOR : OUTPUT_COLOR },
        };
    });
    return { nodes, edges };
}

export function mergeNodes(prev, next) {
    const byId = new Map(prev.map((n) => [n.id, n]));
    return next.map((n) => {
        const old = byId.get(n.id);
        if (!old) return n;
        const kept = {};
        if (old.measured !== undefined) kept.measured = old.measured;
        if (old.dragging !== undefined) kept.dragging = old.dragging;
        return { ...n, ...kept };
    });
}

export function applyFlowNodeChanges(flow, changes) {
    let next = flow;
    for (const change of changes) {
        if (change.type === 'position' && change.position) next = updateNode(next, change.id, { position: change.position });
        else if (change.type === 'remove') next = removeNode(next, change.id);
    }
    return next;
}

export function applyFlowEdgeChanges(flow, changes) {
    let next = flow;
    for (const change of changes) {
        if (change.type === 'remove') next = removeEdge(next, change.id);
    }
    return next;
}

export function connectionKind(sourceHandle) {
    return sourceHandle === 'cb' ? 'callback' : 'output';
}

export function nodeBorderColor({ errors, warnings, resolution }) {
    if (errors.length || (resolution && !resolution.resolved)) return ERROR_COLOR;
    if (warnings.length) return WARNING_COLOR;
    return NODE_COLOR;
}

// Producers show the stream type they emit; engines (given `forwarded`) show
// the source types they pass on.
export function statusText(resolution, forwarded = null) {
    if (!resolution) return 'loading…';
    if (!resolution.resolved) return `unresolved: ${resolution.reason}`;
    const text = forwarded === null
        ? `out: ${shortType(resolution.output)}`
        : `fwd: ${forwarded.length ? forwarded.map(shortType).join(', ') : '—'}`;
    return `${text}${resolution.typed ? '' : ' (untyped)'}`;
}

// The canvas legend: explains symbols the current flow can show. The star
// marks primary cameras in a producer's stream dropdown.
export function legendEntries(flow, catalog) {
    const vehicle = catalog && flow.vehicle ? findVehicle(catalog, flow.vehicle) : null;
    if (!vehicle?.streams.some((s) => s.primary)) return [];
    return [{ symbol: '★', text: 'Primary camera: only one per flow, since primary cameras cannot stream at the same time' }];
}

// A palette engine item's tooltip, from its catalog entry.
export function paletteTitle(engine) {
    const text = `accepts ${engine.accepts.map(shortType).join(', ')} · events: ${engine.events.map((e) => e.label).join(', ')}`;
    return engine.problem ? `${text} · ${engine.problem}` : text;
}
