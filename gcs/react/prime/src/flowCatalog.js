// The Flow Builder's view of what each daemon in the roster runs: its
// vehicles (and their streams) and engines (and the types they accept and
// produce), from GET /api/flows/catalog -- see
// docs/superpowers/specs/2026-10-16-gcs-flow-builder-design.md. A catalog is
// one entry per roster daemon, in roster order; `reachable: false` means
// that daemon's entry can't be used, for whatever reason `error` gives.
import { daemonRequest, describeFailure, query } from './daemonApi.js';

export async function fetchDaemonCatalog(daemon) {
    const result = await daemonRequest('GET', `/api/flows/catalog?${query({ address: daemon.address })}`);
    const base = { name: daemon.name, address: daemon.address };
    const error = describeFailure(result);
    if (error) return { ...base, reachable: false, error, vehicles: [], engines: [] };
    return {
        ...base,
        reachable: true,
        error: null,
        vehicles: result.body.vehicles ?? [],
        engines: result.body.engines ?? [],
    };
}

export function fetchCatalog(daemons) {
    return Promise.all(daemons.map(fetchDaemonCatalog));
}

// Refreshes can overlap (a Refresh click while a roster change is still
// loading); only the most recent request's catalog is delivered.
export function createCatalogLoader(onCatalog) {
    let latest = 0;
    return async (daemons) => {
        const request = ++latest;
        const catalog = await fetchCatalog(daemons);
        if (request === latest) onCatalog(catalog);
    };
}

export function findDaemon(catalog, address) {
    return catalog.find((d) => d.address === address) ?? null;
}

export function findVehicle(catalog, vehicle) {
    if (!vehicle) return null;
    const daemon = findDaemon(catalog, vehicle.daemon.address);
    if (!daemon?.reachable) return null;
    return daemon.vehicles.find((v) => v.name === vehicle.name) ?? null;
}

// A protobuf message type by its last path segment, as the UI shows it
// (steeleagle_protocol/v1/messages/frame/RawFrame -> RawFrame).
export function shortType(type) {
    if (type === null || type === undefined) return '—';
    return type.slice(type.lastIndexOf('/') + 1);
}

export function engineLocation(flow, address) {
    return flow.vehicle && flow.vehicle.daemon.address === address ? 'local' : 'remote';
}

// Every resolution has these keys, resolved or not: `output` is a producer's
// stream type and `stream` its catalog entry; `accepts`, `events` (labels),
// `eventTypes` ({label: message type}) and `category` are an engine's.
const EMPTY = { output: null, stream: null, accepts: [], events: [], eventTypes: {}, category: null, typed: true, problem: null };

function unresolved(reason) {
    return { resolved: false, reason, ...EMPTY };
}

// The daemon entry a reference points at, or an unresolved result saying
// why it can't be used.
function daemonFor(catalog, ref) {
    const daemon = findDaemon(catalog, ref.address);
    if (!daemon) return { problem: unresolved(`daemon ${ref.name} is not in the roster`) };
    if (!daemon.reachable) return { problem: unresolved(`daemon ${ref.name} is unreachable`) };
    return { daemon };
}

export function resolveNode(flow, catalog, node) {
    if (node.kind === 'producer') {
        if (!flow.vehicle) return unresolved('no vehicle selected');
        const { daemon, problem } = daemonFor(catalog, flow.vehicle.daemon);
        if (problem) return problem;
        const vehicle = daemon.vehicles.find((v) => v.name === flow.vehicle.name);
        if (!vehicle) return unresolved(`${daemon.name} has no vehicle ${flow.vehicle.name}`);
        const stream = vehicle.streams.find((s) => s.name === node.stream);
        if (!stream) return unresolved(`${flow.vehicle.name} has no stream ${node.stream}`);
        return { resolved: true, reason: null, ...EMPTY, output: stream.type, stream, typed: vehicle.typed, problem: vehicle.problem ?? null };
    }
    const { daemon, problem } = daemonFor(catalog, node.daemon);
    if (problem) return problem;
    const engine = daemon.engines.find((e) => e.name === node.engine);
    if (!engine) return unresolved(`${daemon.name} has no engine ${node.engine}`);
    // Engines have no output type: they forward the source data they receive
    // (flowModel.forwardedTypes).
    return {
        resolved: true,
        reason: null,
        ...EMPTY,
        accepts: engine.accepts,
        events: engine.events.map((e) => e.label),
        eventTypes: Object.fromEntries(engine.events.map((e) => [e.label, e.type])),
        category: engine.category ?? null,
        typed: engine.typed,
        problem: engine.problem ?? null,
        location: engineLocation(flow, node.daemon.address),
    };
}

export function sameVehicle(a, b) {
    return !!a && !!b && a.name === b.name && a.daemon.address === b.daemon.address;
}

export function vehicleKey(vehicle) {
    return `${vehicle.name}@${vehicle.daemon.address}`;
}

// A vehicle's name, plus its daemon only when another vehicle in `among`
// has the same name on a different daemon.
export function vehicleLabel(vehicle, among = []) {
    const clash = among.some((o) => o.name === vehicle.name && o.daemon.address !== vehicle.daemon.address);
    return clash ? `${vehicle.name} @ ${vehicle.daemon.name}` : vehicle.name;
}

// Every vehicle on a reachable daemon, plus the current binding even if its
// daemon is unreachable or gone, so the picker never silently shows nothing.
export function vehicleOptions(catalog, current) {
    const options = catalog
        .filter((d) => d.reachable)
        .flatMap((d) => d.vehicles.map((v) => ({ name: v.name, daemon: { name: d.name, address: d.address } })));
    if (current && !options.some((o) => sameVehicle(o, current))) options.push(current);
    return options;
}
