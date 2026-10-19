import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { DAEMONS_STORAGE_KEY, loadDaemons, saveDaemons, subscribeDaemons } from './daemonRoster.js';

function memoryStorage() {
    const data = new Map();
    return {
        getItem: (k) => (data.has(k) ? data.get(k) : null),
        setItem: (k, v) => data.set(k, String(v)),
        removeItem: (k) => data.delete(k),
    };
}

beforeEach(() => {
    vi.stubGlobal('localStorage', memoryStorage());
    vi.stubGlobal('window', new EventTarget());
});

afterEach(() => {
    vi.unstubAllGlobals();
});

describe('daemonRoster', () => {
    it('loads an empty roster when nothing is stored', () => {
        expect(loadDaemons()).toEqual([]);
    });

    it('round-trips a saved roster', () => {
        const roster = [{ id: '1', name: 'lab-a', address: 'mock://lab-a' }];
        saveDaemons(roster);
        expect(loadDaemons()).toEqual(roster);
        expect(JSON.parse(localStorage.getItem(DAEMONS_STORAGE_KEY))).toEqual(roster);
    });

    it('treats corrupt or non-array storage as empty', () => {
        localStorage.setItem(DAEMONS_STORAGE_KEY, '{not json');
        expect(loadDaemons()).toEqual([]);
        localStorage.setItem(DAEMONS_STORAGE_KEY, '{"a":1}');
        expect(loadDaemons()).toEqual([]);
    });

    it('notifies subscribers on save until they unsubscribe', () => {
        const seen = [];
        const unsubscribe = subscribeDaemons((d) => seen.push(d));
        saveDaemons([{ id: '1', name: 'a', address: 'x' }]);
        unsubscribe();
        saveDaemons([]);
        expect(seen).toEqual([[{ id: '1', name: 'a', address: 'x' }]]);
    });

    it('notifies on cross-tab storage events for the roster key only', () => {
        const seen = [];
        subscribeDaemons((d) => seen.push(d));
        localStorage.setItem(DAEMONS_STORAGE_KEY, '[]');
        const other = new Event('storage');
        other.key = 'something-else';
        window.dispatchEvent(other);
        const mine = new Event('storage');
        mine.key = DAEMONS_STORAGE_KEY;
        window.dispatchEvent(mine);
        expect(seen).toEqual([[]]);
    });
});
