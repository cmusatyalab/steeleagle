import { describe, it, expect } from 'vitest';
import { groupViewers, viewerLabel } from './presence.js';

const viewer = (id, host) => ({ id, host, ip: host, connected_at: 0 });

describe('groupViewers', () => {
    it('returns no groups for a missing or empty list', () => {
        expect(groupViewers(undefined, 'a')).toEqual([]);
        expect(groupViewers([], 'a')).toEqual([]);
    });

    it('collapses several tabs from one host into a single counted group', () => {
        const groups = groupViewers([viewer('a', 'h1'), viewer('b', 'h1'), viewer('c', 'h2')], 'c');
        expect(groups).toEqual([
            { host: 'h2', count: 1, isYou: true },
            { host: 'h1', count: 2, isYou: false },
        ]);
    });

    it('lists your own host first even when it connected last', () => {
        const groups = groupViewers([viewer('a', 'h1'), viewer('b', 'h2')], 'b');
        expect(groups.map((g) => g.host)).toEqual(['h2', 'h1']);
    });

    it('marks a shared host as yours when one of its tabs is yours', () => {
        const groups = groupViewers([viewer('a', 'h1'), viewer('b', 'h1')], 'b');
        expect(groups).toEqual([{ host: 'h1', count: 2, isYou: true }]);
    });
});

describe('viewerLabel', () => {
    it('shows a bare host for a single other viewer', () => {
        expect(viewerLabel({ host: 'h1', count: 1, isYou: false })).toBe('h1');
    });

    it('appends the tab count and the you marker', () => {
        expect(viewerLabel({ host: 'h1', count: 3, isYou: true })).toBe('h1 (you) ×3');
    });
});
