import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { missionRequestBody, renderDsl } from './missionGraph.js';

const node = (id, instance_id, type_name, params = {}) => ({ id, data: { instance_id, type_name, params } });

describe('missionRequestBody', () => {
    it('keys nodes, edges and the start state by instance_id', () => {
        const nodes = [node('n1', 'takeoff', 'TakeOff', { Altitude: 5 }), node('n2', 'land', 'Land')];
        const edges = [
            { source: 'n1', target: 'n2', data: { eventId: 'low' } },
            { source: 'n2', target: 'n2' },
        ];
        const events = [{ instance_id: 'low', type_name: 'Battery', params: {} }];

        expect(missionRequestBody(nodes, edges, events, 'n1')).toEqual({
            nodes: [
                { instance_id: 'takeoff', type_name: 'TakeOff', params: { Altitude: 5 } },
                { instance_id: 'land', type_name: 'Land', params: {} },
            ],
            events,
            edges: [
                { source: 'takeoff', event_id: 'low', target: 'land' },
                { source: 'land', event_id: 'done', target: 'land' },
            ],
            start_id: 'takeoff',
        });
    });

    it('leaves start_id undefined without a start node', () => {
        expect(missionRequestBody([node('n1', 'a', 'Land')], [], [], null).start_id).toBeUndefined();
    });
});

describe('renderDsl', () => {
    beforeEach(() => {
        vi.stubGlobal('window', { location: { protocol: 'http:', host: 'gcs.example:8002' } });
    });
    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it('posts the graph and returns the DSL text', async () => {
        const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ dsl: 'Actions:\n' }), { status: 200 }));
        vi.stubGlobal('fetch', fetchMock);

        await expect(renderDsl({ nodes: [] })).resolves.toBe('Actions:\n');

        const [url, init] = fetchMock.mock.calls[0];
        expect(url).toBe('http://gcs.example:8002/api/render_dsl');
        expect(init.method).toBe('POST');
        expect(JSON.parse(init.body)).toEqual({ nodes: [] });
    });

    it('throws the backend detail on failure', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
            new Response(JSON.stringify({ detail: 'FSM compiler unavailable: no go' }), { status: 503 }),
        ));

        await expect(renderDsl({})).rejects.toThrow('FSM compiler unavailable: no go');
    });

    it('stringifies structured validation details', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
            new Response(JSON.stringify({ detail: [{ loc: ['body', 'nodes'], msg: 'Field required' }] }), { status: 422 }),
        ));

        await expect(renderDsl({})).rejects.toThrow('Field required');
    });
});
