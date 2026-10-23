// Flow documents for the Plan page's Flow Builder -- see
// docs/superpowers/specs/2026-10-16-gcs-flow-builder-design.md.
//
// A flow is bound to one vehicle; its producers are that vehicle's streams
// and its engines are engine services on any daemon in the roster. The
// document stores references only (stream name, engine name + daemon);
// types and events are looked up in the catalog (flowCatalog.js) whenever
// they're needed, so a flow loaded after the setup changed shows what no
// longer resolves rather than silently dropping it. Every function here is
// pure: it returns a new flow and never mutates its input.
import { engineLocation, findVehicle, resolveNode, shortType } from './flowCatalog.js';

export const SCHEMA_VERSION = 1;
export const DEFAULT_TIMEOUT = '1s';
export const DEFAULT_TOKENS = 1;

export function emptyFlow() {
    return { schemaVersion: SCHEMA_VERSION, name: 'untitled-flow', vehicle: null, nodes: [], edges: [] };
}

// Ids are a kind prefix plus a number ("p1", "e2", "x3"), one past the
// highest in use, so they stay short and readable in exported JSON.
function nextId(items, prefix) {
    const used = items
        .map((item) => item.id)
        .filter((id) => id.startsWith(prefix))
        .map((id) => Number(id.slice(prefix.length)))
        .filter(Number.isInteger);
    return `${prefix}${Math.max(0, ...used) + 1}`;
}

export function nodeById(flow, id) {
    return flow.nodes.find((n) => n.id === id) ?? null;
}

export function nodeLabel(flow, node) {
    if (node.kind === 'producer') return `${flow.vehicle?.name ?? '?'}.${node.stream}`;
    return `${node.engine} @ ${node.daemon.name}`;
}

// The name Gabriel knows a node by. Engines running alongside the vehicle
// are prefixed with its name, matching the flows run against the new
// Gabriel (e.g. "harpy.yolo"); remote engines are shared, so they aren't.
export function exportName(flow, node) {
    if (node.kind === 'producer') return `${flow.vehicle.name}.${node.stream}`;
    return engineLocation(flow, node.daemon.address) === 'local' ? `${flow.vehicle.name}.${node.engine}` : node.engine;
}

function placedStreams(flow) {
    return new Set(flow.nodes.filter((n) => n.kind === 'producer').map((n) => n.stream));
}

// The producer (other than `exceptId`) on a primary camera, if any. Primary
// cameras can't stream alongside each other, so a flow has at most one.
function primaryProducer(flow, catalog, exceptId) {
    const vehicle = findVehicle(catalog, flow.vehicle);
    const primary = new Set(vehicle?.streams.filter((s) => s.primary).map((s) => s.name) ?? []);
    return flow.nodes.find((n) => n.kind === 'producer' && n.id !== exceptId && primary.has(n.stream));
}

// The streams a producer can be on: the bound vehicle's streams no other
// producer uses (plus `nodeId`'s own, even if the catalog lacks it), with
// primary cameras disabled while another producer is on one.
export function streamChoices(flow, catalog, nodeId = null) {
    const vehicle = findVehicle(catalog, flow.vehicle);
    const own = nodeId && nodeById(flow, nodeId)?.stream;
    const others = new Set(flow.nodes.filter((n) => n.kind === 'producer' && n.id !== nodeId).map((n) => n.stream));
    const blocker = primaryProducer(flow, catalog, nodeId);
    const choices = (vehicle?.streams ?? [])
        .filter((s) => !others.has(s.name))
        .map((s) => {
            const disabled = Boolean(s.primary && blocker);
            return {
                name: s.name,
                primary: Boolean(s.primary),
                disabled,
                reason: disabled ? `${nodeLabel(flow, blocker)} is already streaming a primary camera` : null,
            };
        });
    if (own && !choices.some((c) => c.name === own)) {
        choices.unshift({ name: own, primary: false, disabled: false, reason: null });
    }
    return choices;
}

// What a new producer could be on: unplaced streams that aren't blocked.
export function availableStreams(flow, catalog) {
    return streamChoices(flow, catalog).filter((c) => !c.disabled).map((c) => c.name);
}

export function isEnginePlaced(flow, address, engine) {
    return flow.nodes.some((n) => n.kind === 'engine' && n.daemon.address === address && n.engine === engine);
}

export function addProducer(flow, stream, position) {
    if (!flow.vehicle) throw new Error('Select a vehicle first');
    if (placedStreams(flow).has(stream)) throw new Error(`${flow.vehicle.name}.${stream} is already on the canvas`);
    const node = { id: nextId(flow.nodes, 'p'), kind: 'producer', stream, tokens: DEFAULT_TOKENS, position };
    return { ...flow, nodes: [...flow.nodes, node] };
}

export function addEngine(flow, daemon, engine, position) {
    if (isEnginePlaced(flow, daemon.address, engine)) throw new Error(`${engine} @ ${daemon.name} is already on the canvas`);
    const node = {
        id: nextId(flow.nodes, 'e'),
        kind: 'engine',
        engine,
        daemon: { name: daemon.name, address: daemon.address },
        position,
    };
    return { ...flow, nodes: [...flow.nodes, node] };
}

export function updateNode(flow, id, patch) {
    return { ...flow, nodes: flow.nodes.map((n) => (n.id === id ? { ...n, ...patch } : n)) };
}

export function updateEdge(flow, id, patch) {
    return { ...flow, edges: flow.edges.map((e) => (e.id === id ? { ...e, ...patch } : e)) };
}

export function removeNode(flow, id) {
    return {
        ...flow,
        nodes: flow.nodes.filter((n) => n.id !== id),
        edges: flow.edges.filter((e) => e.source !== id && e.target !== id),
    };
}

export function removeEdge(flow, id) {
    return { ...flow, edges: flow.edges.filter((e) => e.id !== id) };
}

// Producers are streams of the bound vehicle, so binding a different
// vehicle drops them (and their edges); engines stay.
export function setVehicle(flow, vehicle) {
    const same = flow.vehicle && vehicle && flow.vehicle.name === vehicle.name
        && flow.vehicle.daemon.address === vehicle.daemon.address;
    if (same) return { ...flow, vehicle };
    const producers = new Set(flow.nodes.filter((n) => n.kind === 'producer').map((n) => n.id));
    return {
        ...flow,
        vehicle,
        nodes: flow.nodes.filter((n) => !producers.has(n.id)),
        edges: flow.edges.filter((e) => !producers.has(e.source) && !producers.has(e.target)),
    };
}

// --- JSON import/export ----------------------------------------------------

const isObject = (v) => !!v && typeof v === 'object' && !Array.isArray(v);
const isDaemonRef = (v) => isObject(v) && typeof v.name === 'string' && typeof v.address === 'string';
const isPosition = (v) => isObject(v) && Number.isFinite(v.x) && Number.isFinite(v.y);

function parseNode(n) {
    if (n.kind === 'producer') {
        if (typeof n.stream !== 'string') throw new Error(`node ${n.id}: producer nodes need a stream name`);
        return { id: n.id, kind: 'producer', stream: n.stream, tokens: n.tokens ?? DEFAULT_TOKENS, position: n.position };
    }
    if (n.kind === 'engine') {
        if (typeof n.engine !== 'string' || !isDaemonRef(n.daemon)) {
            throw new Error(`node ${n.id}: engine nodes need an engine name and daemon {name, address}`);
        }
        return {
            id: n.id,
            kind: 'engine',
            engine: n.engine,
            daemon: { name: n.daemon.name, address: n.daemon.address },
            position: n.position,
        };
    }
    throw new Error(`node ${n.id}: unknown kind ${JSON.stringify(n.kind)}`);
}

function parseEdge(e) {
    const base = { id: e.id, kind: e.kind, source: e.source, target: e.target };
    if (e.kind === 'output') return { ...base, timeout: e.timeout ?? DEFAULT_TIMEOUT };
    if (e.kind === 'callback') {
        if (typeof e.event !== 'string') throw new Error(`edge ${e.id}: callback edges need an event`);
        return { ...base, event: e.event };
    }
    throw new Error(`edge ${e.id}: unknown kind ${JSON.stringify(e.kind)}`);
}

// Checks structure only (well-formed references, known kinds); whether the
// flow makes sense against the current catalog is validateFlow's job, so a
// stale flow still imports and shows what's wrong.
export function parseFlowJson(text) {
    let doc;
    try {
        doc = JSON.parse(text);
    } catch (e) {
        throw new Error(`not valid JSON: ${e.message}`);
    }
    if (!isObject(doc)) throw new Error('not a flow document');
    if (doc.schemaVersion !== SCHEMA_VERSION) {
        throw new Error(`unsupported schemaVersion ${JSON.stringify(doc.schemaVersion)} (expected ${SCHEMA_VERSION})`);
    }
    if (typeof doc.name !== 'string') throw new Error('name must be a string');
    if (doc.vehicle !== null && !(isObject(doc.vehicle) && typeof doc.vehicle.name === 'string' && isDaemonRef(doc.vehicle.daemon))) {
        throw new Error('vehicle must be null or {name, daemon: {name, address}}');
    }
    if (!Array.isArray(doc.nodes) || !Array.isArray(doc.edges)) throw new Error('nodes and edges must be arrays');

    const nodeIds = new Set();
    const nodes = doc.nodes.map((n) => {
        if (!isObject(n) || typeof n.id !== 'string') throw new Error('every node needs a string id');
        if (nodeIds.has(n.id)) throw new Error(`duplicate node id ${n.id}`);
        nodeIds.add(n.id);
        if (!isPosition(n.position)) throw new Error(`node ${n.id}: position must be {x, y}`);
        return parseNode(n);
    });
    const edgeIds = new Set();
    const edges = doc.edges.map((e) => {
        if (!isObject(e) || typeof e.id !== 'string') throw new Error('every edge needs a string id');
        if (edgeIds.has(e.id)) throw new Error(`duplicate edge id ${e.id}`);
        edgeIds.add(e.id);
        if (!nodeIds.has(e.source) || !nodeIds.has(e.target)) throw new Error(`edge ${e.id} references a missing node`);
        return parseEdge(e);
    });
    const vehicle = doc.vehicle && { name: doc.vehicle.name, daemon: { name: doc.vehicle.daemon.name, address: doc.vehicle.daemon.address } };
    return { schemaVersion: SCHEMA_VERSION, name: doc.name, vehicle, nodes, edges };
}

export function serializeFlow(flow) {
    return JSON.stringify(flow, null, 2) + '\n';
}

export function fileBaseName(flow) {
    return flow.name.trim().replace(/[^A-Za-z0-9._-]+/g, '-').replace(/^-+|-+$/g, '') || 'flow';
}

// --- connection rules --------------------------------------------------------

export function acceptsAll(accepts, types) {
    return accepts.includes('*') || types.every((t) => accepts.includes(t));
}

// The source types reaching an engine: its producer inputs' stream types plus
// whatever its engine parent forwards. Engines forward the source data they
// receive; their results travel as events, not along output edges.
export function forwardedTypes(flow, catalog, nodeId, seen = new Set()) {
    if (seen.has(nodeId)) return [];
    seen.add(nodeId);
    const types = [];
    for (const edge of flow.edges) {
        if (edge.kind !== 'output' || edge.target !== nodeId) continue;
        const source = nodeById(flow, edge.source);
        if (!source) continue;
        const arriving = source.kind === 'producer'
            ? [resolveNode(flow, catalog, source)].filter((r) => r.resolved).map((r) => r.output)
            : forwardedTypes(flow, catalog, source.id, seen);
        for (const t of arriving) if (!types.includes(t)) types.push(t);
    }
    return types;
}

// What an output edge from `source` carries.
function arrivingTypes(flow, catalog, source) {
    if (source.kind === 'engine') return forwardedTypes(flow, catalog, source.id);
    const r = resolveNode(flow, catalog, source);
    return r.resolved ? [r.output] : [];
}

// The engine feeding `nodeId` through an output edge, if any. Each engine
// has at most one, so following these links walks a single chain upstream.
function engineParent(flow, nodeId) {
    const edge = flow.edges.find((e) => e.kind === 'output' && e.target === nodeId
        && nodeById(flow, e.source)?.kind === 'engine');
    return edge ? edge.source : null;
}

// The first engine-to-engine edge at or below `startId` in `flow` that would
// carry a type its target doesn't accept *and* that `before` (the flow
// without the new edge) didn't already forward there -- an existing problem
// in a stale flow is validateFlow's to report, not the new edge's fault.
function downstreamProblem(flow, before, catalog, startId) {
    const seen = new Set();
    const queue = [startId];
    while (queue.length) {
        const id = queue.shift();
        if (seen.has(id)) continue;
        seen.add(id);
        for (const edge of flow.edges) {
            if (edge.kind !== 'output' || edge.source !== id) continue;
            const target = nodeById(flow, edge.target);
            if (target?.kind !== 'engine') continue;
            const to = resolveNode(flow, catalog, target);
            if (to.resolved) {
                const already = forwardedTypes(before, catalog, id);
                const missing = forwardedTypes(flow, catalog, id)
                    .filter((t) => !acceptsAll(to.accepts, [t]) && !already.includes(t));
                if (missing.length) {
                    return `this would forward ${missing.map(shortType).join(', ')} to ${nodeLabel(flow, target)}, which does not accept it`;
                }
            }
            queue.push(target.id);
        }
    }
    return null;
}

// `checkDownstream` is for new connections only: validateFlow already checks
// every existing edge against the whole flow's forwarded sets.
function outputProblem(flow, catalog, source, target, checkDownstream = false) {
    if (target.kind !== 'engine') return 'output edges must end at an engine';
    if (source.id === target.id) return 'an engine cannot feed itself';
    const from = resolveNode(flow, catalog, source);
    const to = resolveNode(flow, catalog, target);
    if (!from.resolved || !to.resolved) return 'cannot connect an unresolved node';
    const missing = arrivingTypes(flow, catalog, source).filter((t) => !acceptsAll(to.accepts, [t]));
    if (missing.length) return `${nodeLabel(flow, target)} does not accept ${missing.map(shortType).join(', ')}`;
    if (flow.edges.some((e) => e.kind === 'output' && e.source === source.id && e.target === target.id)) {
        return 'these nodes are already connected';
    }
    if (source.kind === 'engine') {
        if (engineParent(flow, target.id)) return `${nodeLabel(flow, target)} already has an engine input`;
        const seen = new Set();
        for (let cur = source.id; cur && !seen.has(cur); cur = engineParent(flow, cur)) {
            if (cur === target.id) return 'this would create a cycle';
            seen.add(cur);
        }
    }
    if (checkDownstream) {
        const tentative = { ...flow, edges: [...flow.edges, { id: '', kind: 'output', source: source.id, target: target.id }] };
        return downstreamProblem(tentative, flow, catalog, target.id);
    }
    return null;
}

function callbackEvents(flow, sourceId, targetId) {
    return new Set(flow.edges
        .filter((e) => e.kind === 'callback' && e.source === sourceId && e.target === targetId)
        .map((e) => e.event));
}

// `event` null means "is there any event left to connect with".
function callbackProblem(flow, catalog, source, target, event) {
    if (source.kind !== 'engine') return 'callbacks must start at an engine';
    if (source.id === target.id) return 'a callback cannot target its own engine';
    const from = resolveNode(flow, catalog, source);
    const to = resolveNode(flow, catalog, target);
    if (!from.resolved || !to.resolved) return 'cannot connect an unresolved node';
    const label = nodeLabel(flow, source);
    if (from.events.length === 0) return `${label} declares no events`;
    const used = callbackEvents(flow, source.id, target.id);
    if (event === null) {
        return from.events.every((ev) => used.has(ev))
            ? `every event of ${label} already has a callback to ${nodeLabel(flow, target)}`
            : null;
    }
    if (!from.events.includes(event)) return `${label} does not emit ${event}`;
    if (used.has(event)) return `a ${event} callback to ${nodeLabel(flow, target)} already exists`;
    return null;
}

export function canConnect(flow, catalog, sourceId, targetId, kind) {
    const source = nodeById(flow, sourceId);
    const target = nodeById(flow, targetId);
    if (!source || !target) return 'unknown node';
    return kind === 'callback'
        ? callbackProblem(flow, catalog, source, target, null)
        : outputProblem(flow, catalog, source, target, true);
}

export function addEdge(flow, catalog, sourceId, targetId, kind) {
    const problem = canConnect(flow, catalog, sourceId, targetId, kind);
    if (problem) throw new Error(problem);
    const base = { id: nextId(flow.edges, 'x'), kind, source: sourceId, target: targetId };
    let edge;
    if (kind === 'callback') {
        const { events } = resolveNode(flow, catalog, nodeById(flow, sourceId));
        const used = callbackEvents(flow, sourceId, targetId);
        edge = { ...base, event: events.find((ev) => !used.has(ev)) };
    } else {
        edge = { ...base, timeout: DEFAULT_TIMEOUT };
    }
    return { ...flow, edges: [...flow.edges, edge] };
}

// --- validation ----------------------------------------------------------------

const TIMEOUT_PATTERN = /^\d+(\.\d+)?(ms|s|m)$/;

function nodeKey(node) {
    return node.kind === 'producer' ? `p:${node.stream}` : `e:${node.daemon.address}/${node.engine}`;
}

// Why an existing edge is invalid, checked as if it were being added to the
// flow without it, so it isn't refused for duplicating itself.
function edgeProblem(flow, catalog, edge) {
    const others = { ...flow, edges: flow.edges.filter((e) => e.id !== edge.id) };
    const source = nodeById(flow, edge.source);
    const target = nodeById(flow, edge.target);
    if (edge.kind === 'callback') return callbackProblem(others, catalog, source, target, edge.event);
    return outputProblem(others, catalog, source, target)
        ?? (TIMEOUT_PATTERN.test(edge.timeout) ? null : `timeout "${edge.timeout}" is not a duration like 500ms, 1s, or 2m`);
}

export function validateFlow(flow, catalog) {
    const errors = [];
    const warnings = [];
    if (!flow.vehicle) errors.push({ message: 'No vehicle selected' });
    // The vehicle's plugin-file problem (a dropped camera, no plugin file),
    // once: its producers' own warnings don't repeat it.
    const vehicleProblem = catalog && flow.vehicle && findVehicle(catalog, flow.vehicle)?.problem;
    if (vehicleProblem) warnings.push({ message: `${flow.vehicle.name}: ${vehicleProblem}` });

    const resolved = new Set();
    const seen = new Set();
    for (const node of flow.nodes) {
        const label = nodeLabel(flow, node);
        const key = nodeKey(node);
        if (seen.has(key)) errors.push({ nodeId: node.id, message: `${label} appears more than once` });
        seen.add(key);
        if (node.kind === 'producer' && !(Number.isInteger(node.tokens) && node.tokens >= 1)) {
            errors.push({ nodeId: node.id, message: `${label}: tokens must be a whole number of at least 1` });
        }
        const resolution = resolveNode(flow, catalog, node);
        if (!resolution.resolved) {
            errors.push({ nodeId: node.id, message: `${label}: ${resolution.reason}` });
            continue;
        }
        resolved.add(node.id);
        const engineProblem = node.kind === 'engine' ? resolution.problem : null;
        if (!resolution.typed) {
            const why = engineProblem ? ` (${engineProblem})` : '';
            warnings.push({ nodeId: node.id, message: `${label}: no type information${why}; connections are not type-checked` });
        } else if (engineProblem) {
            warnings.push({ nodeId: node.id, message: `${label}: ${engineProblem}` });
        }
        if (node.kind === 'engine' && !flow.edges.some((e) => e.kind === 'output' && e.target === node.id)) {
            warnings.push({ nodeId: node.id, message: `Nothing feeds into ${label}` });
        }
    }

    const primaries = flow.nodes.filter((n) => n.kind === 'producer' && resolved.has(n.id) && resolveNode(flow, catalog, n).stream?.primary);
    for (const node of primaries.slice(1)) {
        errors.push({
            nodeId: node.id,
            message: `${nodeLabel(flow, node)} and ${nodeLabel(flow, primaries[0])} are both primary cameras; only one can stream at a time`,
        });
    }

    for (const edge of flow.edges) {
        if (!resolved.has(edge.source) || !resolved.has(edge.target)) continue;
        const problem = edgeProblem(flow, catalog, edge);
        if (problem) {
            const where = `${nodeLabel(flow, nodeById(flow, edge.source))} → ${nodeLabel(flow, nodeById(flow, edge.target))}`;
            errors.push({ edgeId: edge.id, message: `${where}: ${problem}` });
        }
    }

    if (flow.vehicle) {
        const byName = new Map();
        for (const node of flow.nodes) {
            const name = exportName(flow, node);
            byName.set(name, [...(byName.get(name) ?? []), node]);
        }
        for (const [name, nodes] of byName) {
            if (nodes.length > 1 && new Set(nodes.map(nodeKey)).size > 1) {
                errors.push({
                    nodeId: nodes[1].id,
                    message: `${nodes.map((n) => nodeLabel(flow, n)).join(' and ')} would both be named "${name}" in Gabriel TOML`,
                });
            }
        }
    }
    return { errors, warnings };
}

// --- Gabriel TOML export -----------------------------------------------------------

// JSON string escaping is valid TOML basic-string escaping.
const tomlString = (s) => JSON.stringify(s);

// The [[gabriel.flow.*]] form the new Gabriel reads. Callbacks have no TOML
// representation yet, so they're left out (and counted in a comment).
export function toGabrielToml(flow, catalog) {
    const { errors } = validateFlow(flow, catalog);
    if (errors.length) throw new Error(`flow has ${errors.length} error(s); fix them before exporting TOML`);

    const byId = new Map(flow.nodes.map((n) => [n.id, n]));
    const name = (node) => tomlString(exportName(flow, node));
    const producers = flow.nodes.filter((n) => n.kind === 'producer').flatMap((n) => [
        '[[gabriel.flow.producers]]',
        `name = ${name(n)}`,
        ...(n.tokens !== DEFAULT_TOKENS ? [`tokens = ${n.tokens}`] : []),
    ]);
    const engines = flow.nodes.filter((n) => n.kind === 'engine').flatMap((n) => [
        '[[gabriel.flow.engines]]',
        `name = ${name(n)}`,
        `location = ${tomlString(engineLocation(flow, n.daemon.address))}`,
    ]);
    const edges = flow.edges.filter((e) => e.kind === 'output').flatMap((e) => [
        '[[gabriel.flow.edges]]',
        `from = ${name(byId.get(e.source))}`,
        `to = ${name(byId.get(e.target))}`,
        `timeout = ${tomlString(e.timeout)}`,
    ]);

    const callbacks = flow.edges.filter((e) => e.kind === 'callback').length;
    const header = callbacks
        ? `# ${callbacks} callback edge(s) omitted: Gabriel flow TOML has no callback representation yet.\n\n`
        : '';
    const sections = [producers, engines, edges].filter((lines) => lines.length).map((lines) => lines.join('\n'));
    return header + sections.join('\n\n') + '\n';
}
