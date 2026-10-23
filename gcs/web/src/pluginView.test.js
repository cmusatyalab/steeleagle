import { describe, it, expect } from 'vitest';
import { configGroups, formatUptime, formatValue, hasRunState, logSourcesFor, runStatus, runtimeLabel, sourceIcon, sourceLabel } from './pluginView.js';

describe('pluginView', () => {
    it('labels runtimes, including unknown ones verbatim', () => {
        expect([runtimeLabel('sandbox'), runtimeLabel('podman'), runtimeLabel(null)]).toEqual(['Sandbox', 'podman', '—']);
    });

    it('labels and icons sources', () => {
        expect(sourceLabel({ kind: 'image', url: 'docker.io/x/y', tag: 'v1' })).toBe('docker.io/x/y@v1');
        expect(sourceLabel({ kind: 'repo', url: 'https://x/y.git', tag: '' })).toBe('https://x/y.git');
        expect(sourceLabel(null)).toBe('—');
        expect([sourceIcon({ kind: 'image' }), sourceIcon({ kind: 'repo' }), sourceIcon({ kind: null })]).toEqual(['pi pi-box', 'pi pi-code', 'pi pi-link']);
    });

    it('maps a service to its log sources', () => {
        expect(logSourcesFor({ name: 'harpy', category: 'vehicle' })).toEqual(['harpy-driver', 'harpy-mission']);
        expect(logSourcesFor({ name: 'detector', category: 'engine' })).toEqual(['detector']);
    });

    it('formats uptime to its two largest units', () => {
        expect([formatUptime(null), formatUptime(0), formatUptime(45.9), formatUptime(60), formatUptime(754)])
            .toEqual(['—', '0s', '45s', '1m', '12m 34s']);
        expect([formatUptime(3600 * 3 + 60 * 4 + 5), formatUptime(86400 * 2 + 3600 * 5 + 99)]).toEqual(['3h 4m', '2d 5h']);
    });

    it('describes run state, unknown when the daemon cannot report it', () => {
        expect(runStatus({ running: true })).toEqual({ label: 'Running', severity: 'success' });
        expect(runStatus({ running: false })).toEqual({ label: 'Stopped', severity: 'danger' });
        expect(runStatus({ running: null })).toBeNull();
        expect(runStatus({})).toBeNull();
    });

    it('knows whether a daemon reported any run state', () => {
        expect(hasRunState([{ running: null }, {}])).toBe(false);
        expect(hasRunState([{ running: null }, { running: false }])).toBe(true);
        expect(hasRunState([])).toBe(false);
    });

    it('formats values', () => {
        expect([formatValue('a'), formatValue(1.5), formatValue(true), formatValue(['x', 2])]).toEqual(['a', '1.5', 'true', '["x",2]']);
    });

    it('groups a vehicle entry into plugin, args, sim, vehicle args and other', () => {
        const groups = configGroups({
            category: 'vehicle',
            section: {
                name: 'harpy',
                plugin: { id: 'anafi', runtime: 'container', source: { kind: 'image', url: 'docker.io/x/a', tag: 'v4' }, args: { fps: 30 }, extra: { override: '' } },
                instance_fields: { sim: { default: false, lat: 40.4 }, args: { ip: '10.0.0.1' }, note: 'n' },
            },
        });
        expect(groups).toEqual([
            { title: 'Plugin', rows: [['ID', 'anafi'], ['Runtime', 'Container'], ['Image', 'docker.io/x/a@v4'], ['override', '']] },
            { title: 'Plugin args', rows: [['fps', '30']] },
            { title: 'Sim', rows: [['default', 'false'], ['lat', '40.4']] },
            { title: 'Vehicle args', rows: [['ip', '10.0.0.1']] },
            { title: 'Other', rows: [['note', 'n']] },
        ]);
    });

    it('keeps sim and args under other for non-vehicles and shows empty plugin args', () => {
        const groups = configGroups({
            category: 'engine',
            section: { name: 'd', plugin: { id: 'yolo', runtime: null, source: null, args: {}, extra: {} }, instance_fields: { args: { gpu: 0 } } },
        });
        expect(groups.map((g) => g.title)).toEqual(['Plugin', 'Plugin args', 'Other']);
        expect(groups[0].rows).toEqual([['ID', 'yolo'], ['Runtime', '—'], ['Source', '—']]);
        expect(groups[1].rows).toEqual([]);
        expect(groups[2].rows).toEqual([['args', '{"gpu":0}']]);
    });
});
