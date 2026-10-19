// Editor state for the Configure dialog, converted to and from the backend's
// form model (GET/PUT /api/daemons/config, FormModel in
// gcs/react/backend/app/eagled_routes.py):
//
//   { settings: { hostname, vehicle_port_base, ... },     // null = not set
//     instances: { vehicle: [section], engine: [...], ... } }
//
// Validation mirrors the backend's so the dialog can't send something the
// route would reject. Section fields the editor doesn't show (plugin.extra,
// unknown instance keys) pass through untouched via each instance's `base`.

import { fromRows, toRows } from './kvArgs.js';

export const CATEGORIES = ['vehicle', 'engine', 'monitor', 'commander', 'simulator', 'database', 'extra'];
export const CATEGORY_LABELS = {
    vehicle: 'Vehicles',
    engine: 'Engines',
    monitor: 'Monitors',
    commander: 'Commander',
    simulator: 'Simulator',
    database: 'Database',
    extra: 'Extras',
};
export const RUNTIMES = ['process', 'sandbox', 'container'];

// Daemon-wide settings, in config.toml order. `key` is the API name.
export const SETTINGS = [
    { key: 'hostname', label: 'Hostname', type: 'text' },
    { key: 'vehicle_port_base', label: 'Vehicle Port Base', type: 'port' },
    { key: 'gabriel_port', label: 'Gabriel Port', type: 'port' },
    { key: 'swarm_controller_port', label: 'Swarm Controller Port', type: 'port' },
    { key: 'headless', label: 'Headless', type: 'boolean' },
    { key: 'auto_run', label: 'Auto Run', type: 'boolean' },
    { key: 'auto_install', label: 'Auto Install', type: 'boolean' },
];

const NAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;
const NAME_MAX_LENGTH = 64;
const SIM_COORDS = ['lat', 'lon', 'alt'];
const SIM_KEYS = ['default', ...SIM_COORDS];

let nextKey = 0;
const instanceKey = () => `inst-${nextKey++}`;

export function validateName(value) {
    const name = value.trim();
    if (!name) return 'Required';
    if (name.length > NAME_MAX_LENGTH) return `At most ${NAME_MAX_LENGTH} characters`;
    if (!NAME_PATTERN.test(name)) return 'Letters, digits, ".", "_" and "-" only; must start with a letter or digit';
    return null;
}

const isNumber = (v) => typeof v === 'number' && !Number.isNaN(v);

// The [vehicles.sim] table's editable part; unset coordinates are left out
// rather than written as nulls (TOML has none).
export function simFields(sim) {
    const out = { default: !!sim.default };
    for (const key of SIM_COORDS) {
        if (isNumber(sim[key])) out[key] = sim[key];
    }
    return out;
}

// A simulated vehicle needs an origin, so each coordinate is required.
export function simErrors(sim) {
    const errors = {};
    if (!sim.default) return errors;
    for (const key of SIM_COORDS) {
        if (!isNumber(sim[key])) errors[key] = 'Required for a simulated vehicle';
    }
    return errors;
}

function instanceState(category, section) {
    const plugin = section.plugin ?? {};
    const fields = section.instance_fields ?? {};
    return {
        key: instanceKey(),
        category,
        base: section,
        name: section.name ?? '',
        pluginId: plugin.id ?? '',
        runtime: plugin.runtime ?? null,
        sourceKind: plugin.source?.kind ?? 'repo',
        url: plugin.source?.url ?? '',
        tag: plugin.source?.tag ?? '',
        argRows: toRows(plugin.args),
        vehicleArgRows: toRows(fields.args),
        sim: { default: false, lat: null, lon: null, alt: null, ...(fields.sim ?? {}) },
    };
}

export function newInstance(category) {
    const sim = category === 'vehicle' ? { sim: { default: false } } : {};
    return instanceState(category, {
        name: '',
        plugin: { id: '', runtime: 'process', source: null, args: {}, extra: {} },
        instance_fields: sim,
    });
}

// A copy of an instance's plugin settings under a blank name: the usual way
// to add another vehicle of a kind already configured.
export function duplicateInstance(inst) {
    const { section } = instanceSection(inst);
    return instanceState(inst.category, { ...section, name: '' });
}

export function formToState(form) {
    const settings = {};
    for (const { key } of SETTINGS) settings[key] = form.settings?.[key] ?? null;
    const instances = {};
    for (const category of CATEGORIES) {
        instances[category] = (form.instances?.[category] ?? []).map((s) => instanceState(category, s));
    }
    return { settings, instances };
}

function instanceSection(inst) {
    const args = fromRows(inst.argRows);
    const vehicleArgs = fromRows(inst.vehicleArgRows);
    const errors = {};
    const nameError = validateName(inst.name);
    if (nameError) errors.name = nameError;
    const pluginId = inst.pluginId.trim();
    const url = inst.url.trim();
    if (pluginId) {
        const idError = validateName(pluginId);
        if (idError) errors.pluginId = idError;
    } else if (!url) {
        errors.pluginId = 'Give a plugin ID or a source URL';
    }
    const kind = inst.runtime === 'container' ? inst.sourceKind : 'repo';
    if (Object.keys(args.errors).length) errors.args = args.errors;

    const baseFields = inst.base.instance_fields ?? {};
    const instanceFields = { ...baseFields };
    if (inst.category === 'vehicle') {
        if (Object.keys(vehicleArgs.errors).length) errors.vehicleArgs = vehicleArgs.errors;
        const sim = simFields(inst.sim);
        const simErrs = simErrors(inst.sim);
        if (Object.keys(simErrs).length) errors.sim = simErrs;
        // Write [vehicles.sim] only if the config had one or it now says something.
        if ('sim' in baseFields || sim.default || Object.keys(sim).length > 1) {
            const otherSim = Object.fromEntries(Object.entries(baseFields.sim ?? {}).filter(([k]) => !SIM_KEYS.includes(k)));
            instanceFields.sim = { ...otherSim, ...sim };
        }
        if (inst.vehicleArgRows.length > 0 || 'args' in baseFields) instanceFields.args = vehicleArgs.value;
    }
    const section = {
        name: inst.name.trim(),
        plugin: {
            ...inst.base.plugin,
            id: pluginId,
            runtime: inst.runtime,
            source: url ? { kind, url, tag: inst.tag.trim() } : null,
            args: args.value,
            extra: inst.base.plugin?.extra ?? {},
        },
        instance_fields: instanceFields,
    };
    return { section, errors };
}

function settingErrors(settings) {
    const errors = {};
    for (const { key, type } of SETTINGS) {
        const value = settings[key];
        if (type === 'port' && value !== null && (!Number.isInteger(value) || value < 1 || value > 65535)) {
            errors[key] = 'A port from 1 to 65535';
        }
    }
    return errors;
}

// Returns { form, errors }. errors is
//   { settings: { key: message }, instances: { instanceKey: { field: ... } } }
// with empty objects when valid; `form` is only meaningful to send then.
export function stateToForm(state) {
    const settings = {};
    for (const { key, type } of SETTINGS) {
        const value = state.settings[key];
        settings[key] = type === 'text' ? (value?.trim() || null) : value;
    }
    const errors = { settings: settingErrors(state.settings), instances: {} };
    const instances = {};
    for (const category of CATEGORIES) {
        const seen = new Map();
        instances[category] = state.instances[category].map((inst) => {
            const { section, errors: instErrors } = instanceSection(inst);
            if (section.name && seen.has(section.name)) instErrors.name = `Duplicate ${category} name`;
            seen.set(section.name, true);
            if (Object.keys(instErrors).length) errors.instances[inst.key] = instErrors;
            return section;
        });
    }
    return { form: { settings, instances }, errors };
}

export function hasErrors(errors) {
    return Object.keys(errors.settings).length > 0 || Object.keys(errors.instances).length > 0;
}
