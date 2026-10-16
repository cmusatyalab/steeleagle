import { describe, it, expect, afterEach, vi } from 'vitest';
import { daemonRequest, describeFailure, formatDetail, query } from './daemonApi.js';

afterEach(() => {
    vi.unstubAllGlobals();
});

function stubFetch(impl) {
    vi.stubGlobal('window', { location: { protocol: 'http:', host: 'gcs:8000' } });
    const fetch = vi.fn(impl);
    vi.stubGlobal('fetch', fetch);
    return fetch;
}

describe('daemonRequest', () => {
    it('sends JSON and returns status and parsed body', async () => {
        const fetch = stubFetch(async () => ({ status: 200, json: async () => ({ ok: true }) }));
        const result = await daemonRequest('PUT', '/api/daemons/x', { a: 1 });
        expect(result).toEqual({ status: 200, body: { ok: true } });
        const [url, init] = fetch.mock.calls[0];
        expect(url).toBe('http://gcs:8000/api/daemons/x');
        expect(init).toMatchObject({ method: 'PUT', body: '{"a":1}', headers: { 'Content-Type': 'application/json' } });
    });

    it('omits the body for GET', async () => {
        const fetch = stubFetch(async () => ({ status: 200, json: async () => ({}) }));
        await daemonRequest('GET', '/x');
        expect(fetch.mock.calls[0][1].body).toBeUndefined();
    });

    it('never rejects', async () => {
        stubFetch(async () => { throw new Error('offline'); });
        expect(await daemonRequest('GET', '/x')).toEqual({ status: 0, body: null, networkError: 'offline' });
        stubFetch(async () => ({ status: 502, json: async () => { throw new SyntaxError('html'); } }));
        expect(await daemonRequest('GET', '/x')).toEqual({ status: 502, body: null });
    });
});

describe('describeFailure', () => {
    it.each([
        [{ status: 200, body: { reachable: true, ok: true } }, null],
        [{ status: 200, body: { raw_toml: 'x' } }, null],
        [{ status: 0, body: null, networkError: 'offline' }, 'Request failed: offline'],
        [{ status: 502, body: null }, 'Server returned a non-JSON response (status 502).'],
        [{ status: 422, body: { detail: { message: 'bad', line: 2, column: 5 } } }, 'bad (line 2, column 5)'],
        [{ status: 500, body: { detail: 'boom' } }, 'Request rejected (HTTP 500).'],
        [{ status: 200, body: { reachable: false, error: 'down' } }, 'down'],
        [{ status: 200, body: { reachable: false } }, 'Daemon unreachable'],
        [{ status: 200, body: { reachable: true, ok: false, error: 'nope' } }, 'nope'],
    ])('%j -> %j', (result, expected) => {
        expect(describeFailure(result)).toBe(expected);
    });
});

describe('formatDetail', () => {
    it('formats our detail objects, pydantic error lists, and strings', () => {
        expect(formatDetail({ message: 'renaming is not supported', line: null, column: null })).toBe('renaming is not supported');
        expect(formatDetail([{ loc: ['body', 'section', 'name'], msg: 'String should match pattern' }])).toBe('section.name: String should match pattern');
        expect(formatDetail('plain')).toBe('plain');
    });
});

describe('query', () => {
    it('encodes parameters', () => {
        expect(query({ address: 'mock://lab-a', name: 'a b' })).toBe('address=mock%3A%2F%2Flab-a&name=a+b');
    });
});
