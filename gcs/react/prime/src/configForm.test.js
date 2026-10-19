import { describe, expect, it } from 'vitest';
import {
    CATEGORIES,
    CATEGORY_LABELS,
    duplicateInstance,
    formToState,
    hasErrors,
    newInstance,
    simErrors,
    simFields,
    stateToForm,
    validateName,
} from './configForm.js';

const HARPY = {
    name: 'harpy',
    plugin: {
        id: 'parrot_anafi',
        runtime: 'container',
        source: { kind: 'image', url: 'docker.io/x/anafi', tag: 'v4' },
        args: { confidence: 0.5, modes: ['a'] },
        extra: { override: '' },
    },
    instance_fields: { sim: { default: false, lat: 40.4, lon: -79.9, alt: 0, speed: 3 }, args: { ip: '10.0.0.1' }, note: 'x' },
};
const DETECTOR = {
    name: 'detector',
    plugin: { id: 'yolo', runtime: 'process', source: null, args: { model: 'yolov8n' }, extra: {} },
    instance_fields: { gpu: true },
};
const FORM = {
    settings: { hostname: 'eagled', vehicle_port_base: 9000, headless: true },
    instances: { vehicle: [HARPY], engine: [DETECTOR], monitor: [], commander: [], simulator: [], database: [], extra: [] },
};

const SETTINGS_OUT = {
    hostname: 'eagled',
    vehicle_port_base: 9000,
    gabriel_port: null,
    swarm_controller_port: null,
    headless: true,
    auto_run: null,
    auto_install: null,
};

describe('categories', () => {
    it('covers every daemon service category, each with a label', () => {
        expect(CATEGORIES).toEqual(['vehicle', 'engine', 'monitor', 'commander', 'simulator', 'database', 'extra']);
        expect(CATEGORIES.map((c) => CATEGORY_LABELS[c])).toEqual(
            ['Vehicles', 'Engines', 'Monitors', 'Commander', 'Simulator', 'Database', 'Extras']);
    });

    it('gives a form without a category an empty list for it', () => {
        expect(formToState({ settings: {}, instances: { vehicle: [] } }).instances.commander).toEqual([]);
    });
});

describe('formToState / stateToForm', () => {
    it('round-trips a form unchanged, including fields the editor does not show', () => {
        const { form, errors } = stateToForm(formToState(FORM));
        expect(hasErrors(errors)).toBe(false);
        expect(form).toEqual({ ...FORM, settings: SETTINGS_OUT });
    });

    it('applies edits to plugin fields, args and settings', () => {
        const state = formToState(FORM);
        const det = state.instances.engine[0];
        det.argRows[0] = { ...det.argRows[0], value: 'yolov8s' };
        det.url = ' https://x/e.git ';
        det.tag = 'main';
        state.settings.hostname = '  ';
        state.settings.gabriel_port = 9099;

        const { form } = stateToForm(state);

        expect(form.instances.engine[0].plugin).toMatchObject({
            args: { model: 'yolov8s' },
            source: { kind: 'repo', url: 'https://x/e.git', tag: 'main' },
        });
        expect(form.settings.hostname).toBeNull();
        expect(form.settings.gabriel_port).toBe(9099);
    });

    it('treats an image source as a repo when the runtime is not container', () => {
        const state = formToState(FORM);
        state.instances.vehicle[0].runtime = 'process';
        expect(stateToForm(state).form.instances.vehicle[0].plugin.source.kind).toBe('repo');
    });

    it('reports errors per instance and per setting', () => {
        const state = formToState(FORM);
        state.instances.engine.push({ ...newInstance('engine'), name: 'detector' });
        state.instances.vehicle[0].pluginId = '../x';
        state.instances.vehicle[0].sim = { default: true, lat: null, lon: 1, alt: 0 };
        state.settings.vehicle_port_base = 70000;

        const { errors } = stateToForm(state);

        const [harpyKey] = [state.instances.vehicle[0].key];
        const dupKey = state.instances.engine[1].key;
        expect(errors.settings).toEqual({ vehicle_port_base: 'A port from 1 to 65535' });
        expect(Object.keys(errors.instances[harpyKey]).sort()).toEqual(['pluginId', 'sim']);
        expect(errors.instances[dupKey].name).toBe('Duplicate engine name');
        expect(errors.instances[dupKey].pluginId).toMatch(/plugin ID or a source/);
    });

    it('flags bad arg rows on the instance', () => {
        const state = formToState(FORM);
        state.instances.engine[0].argRows.push({ id: 'r', key: '', type: 'string', value: '' });
        const { errors } = stateToForm(state);
        expect(errors.instances[state.instances.engine[0].key].args).toEqual({ r: 'Key is required' });
    });
});

describe('newInstance / duplicateInstance', () => {
    it('starts a vehicle with a sim table and nothing else', () => {
        const inst = { ...newInstance('vehicle'), name: 'osprey', pluginId: 'anafi' };
        const state = { settings: {}, instances: { ...formToState({}).instances, vehicle: [inst] } };
        expect(stateToForm(state).form.instances.vehicle[0]).toEqual({
            name: 'osprey',
            plugin: { id: 'anafi', runtime: 'process', source: null, args: {}, extra: {} },
            instance_fields: { sim: { default: false } },
        });
    });

    it('duplicates plugin settings under a blank name with a fresh key', () => {
        const [harpy] = formToState(FORM).instances.vehicle;
        const copy = duplicateInstance(harpy);
        expect(copy.name).toBe('');
        expect(copy.key).not.toBe(harpy.key);
        expect(copy.pluginId).toBe('parrot_anafi');
        expect(copy.url).toBe('docker.io/x/anafi');
        expect(copy.sim.lat).toBe(40.4);
    });
});

describe('sim helpers', () => {
    it('leaves unset coordinates out and requires them only when simulated', () => {
        expect(simFields({ default: true, lat: 1, lon: null, alt: Number.NaN })).toEqual({ default: true, lat: 1 });
        expect(simErrors({ default: false })).toEqual({});
        expect(Object.keys(simErrors({ default: true, lat: 1 })).sort()).toEqual(['alt', 'lon']);
    });
});

describe('validateName', () => {
    it.each([
        ['', 'Required'],
        ['a'.repeat(65), 'At most 64 characters'],
        ['-x', /Letters/],
        ['ok.name-1', null],
    ])('%s', (name, expected) => {
        const result = validateName(name);
        if (expected instanceof RegExp) expect(result).toMatch(expected);
        else expect(result).toBe(expected);
    });
});
