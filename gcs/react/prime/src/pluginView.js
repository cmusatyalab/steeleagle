// Display helpers for service rows.

const RUNTIME_LABELS = { process: 'Process', sandbox: 'Sandbox', container: 'Container' };

// Unknown runtimes (a daemon config can hold anything) are shown verbatim.
export function runtimeLabel(runtime) {
    if (!runtime) return '—';
    return RUNTIME_LABELS[runtime] ?? runtime;
}

export function sourceLabel(source) {
    if (!source?.url) return '—';
    return source.tag ? `${source.url}@${source.tag}` : source.url;
}

export function sourceIcon(source) {
    if (source?.kind === 'image') return 'pi pi-box';
    if (source?.kind === 'repo') return 'pi pi-code';
    return 'pi pi-link';
}

// The log sources a service writes, as eagled names them: a vehicle's
// driver and mission processes log separately; other services log under
// their own name.
export function logSourcesFor(inst) {
    return inst.category === 'vehicle' ? [`${inst.name}-driver`, `${inst.name}-mission`] : [inst.name];
}

// A service's run state from the daemon's ListServices, as a Tag's label and
// severity; null when the daemon can't report it (running is null).
export function runStatus(inst) {
    if (inst.running === true) return { label: 'Running', severity: 'success' };
    if (inst.running === false) return { label: 'Stopped', severity: 'danger' };
    return null;
}

// Whether a daemon reported run state for any of its services; a daemon
// without ListServices reports none, and the Services tab hides the columns.
export function hasRunState(instances) {
    return instances.some((i) => typeof i.running === 'boolean');
}

const UPTIME_UNITS = [['d', 86400], ['h', 3600], ['m', 60], ['s', 1]];

// Seconds as the two largest non-zero units ("12m 34s", "2d 5h").
export function formatUptime(seconds) {
    if (seconds === null || seconds === undefined) return '—';
    let rest = Math.floor(seconds);
    const parts = [];
    for (const [unit, size] of UPTIME_UNITS) {
        const n = Math.floor(rest / size);
        rest -= n * size;
        if (n > 0 || parts.length > 0) parts.push([n, unit]);
    }
    const shown = parts.slice(0, 2).filter(([n], i) => i === 0 || n > 0);
    return shown.length ? shown.map(([n, unit]) => `${n}${unit}`).join(' ') : '0s';
}

// One config value as display text: strings as-is, everything else (numbers,
// booleans, arrays, tables) as JSON.
export function formatValue(value) {
    return typeof value === 'string' ? value : JSON.stringify(value);
}

// A service's config entry (the form model's section) grouped for the
// Services tab's read-only view: [{ title, rows: [[label, text], ...] }].
// Empty groups are left out, except plugin args, which shows "none".
export function configGroups(inst) {
    const { plugin = {}, instance_fields: fields = {} } = inst.section ?? {};
    const entries = (obj) => Object.entries(obj ?? {}).map(([k, v]) => [k, formatValue(v)]);
    const groups = [{
        title: 'Plugin',
        rows: [
            ['ID', plugin.id || '—'],
            ['Runtime', runtimeLabel(plugin.runtime)],
            [plugin.source?.kind === 'image' ? 'Image' : 'Source', sourceLabel(plugin.source)],
            ...entries(plugin.extra),
        ],
    }, { title: 'Plugin args', rows: entries(plugin.args) }];
    const { sim, args, ...other } = fields;
    if (inst.category === 'vehicle') {
        if (sim) groups.push({ title: 'Sim', rows: entries(sim) });
        if (args) groups.push({ title: 'Vehicle args', rows: entries(args) });
    } else {
        if (sim !== undefined) other.sim = sim;
        if (args !== undefined) other.args = args;
    }
    if (Object.keys(other).length) groups.push({ title: 'Other', rows: entries(other) });
    return groups;
}
