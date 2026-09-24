import { describe, it, expect } from 'vitest';
import { MAX_RECORDS, initialLogState, toRow, advanceCursors, appendRows, filterRows } from './logState.js';

const row = (source, seq, extra = {}) => ({ source, seq, time: new Date(0), level: '', text: `${source}-${seq}`, dropped: 0, ...extra });
const gap = (source, dropped) => ({ source, seq: 0, time: new Date(0), level: '', text: 'gap', dropped });

describe('toRow', () => {
    it('parses the time and defaults optional fields', () => {
        const r = toRow({ source: 'daemon', seq: 3, time: '1970-01-01T00:00:01Z', text: 'hi' });
        expect(r.time.getTime()).toBe(1000);
        expect(r).toMatchObject({ source: 'daemon', seq: 3, level: '', text: 'hi', dropped: 0 });
    });
});

describe('advanceCursors', () => {
    it('advances per source independently', () => {
        let c = {};
        c = advanceCursors(c, row('a', 5));
        c = advanceCursors(c, row('b', 2));
        expect(c).toEqual({ a: 5, b: 2 });
    });

    it('ignores equal or older seqs and returns the same object', () => {
        const c = { a: 5 };
        expect(advanceCursors(c, row('a', 5))).toBe(c);
        expect(advanceCursors(c, row('a', 4))).toBe(c);
    });

    it('ignores gap markers', () => {
        const c = { a: 5 };
        expect(advanceCursors(c, gap('a', 3))).toBe(c);
    });

    it('does not mutate its input', () => {
        const c = { a: 1 };
        advanceCursors(c, row('a', 2));
        expect(c).toEqual({ a: 1 });
    });
});

describe('appendRows', () => {
    it('appends rows with unique keys and does not mutate the old state', () => {
        const s0 = initialLogState();
        const s1 = appendRows(s0, [row('a', 1), row('b', 1)]);
        expect(s0.records).toHaveLength(0);
        expect(s1.records.map((r) => r.key)).toEqual(['a#1', 'b#1']);
    });

    it('gives every gap marker its own key', () => {
        const s = appendRows(initialLogState(), [gap('a', 2), gap('a', 2)]);
        expect(new Set(s.records.map((r) => r.key)).size).toBe(2);
        expect(s.gapCount).toBe(2);
    });

    it('keeps only the newest cap rows', () => {
        const rows = Array.from({ length: 10 }, (_, i) => row('a', i + 1));
        const s = appendRows(initialLogState(), rows, 4);
        expect(s.records.map((r) => r.seq)).toEqual([7, 8, 9, 10]);
    });

    it('defaults the cap to MAX_RECORDS', () => {
        expect(MAX_RECORDS).toBe(5000);
        const rows = Array.from({ length: MAX_RECORDS + 3 }, (_, i) => row('a', i + 1));
        expect(appendRows(initialLogState(), rows).records).toHaveLength(MAX_RECORDS);
    });

    it('returns the same state for no rows', () => {
        const s = initialLogState();
        expect(appendRows(s, [])).toBe(s);
    });
});

describe('filterRows', () => {
    const rows = [row('a', 1, { level: 'info' }), row('a', 2, { level: 'error' }), row('a', 3), gap('a', 1)];

    it('passes everything when no levels are selected', () => {
        expect(filterRows(rows, [])).toBe(rows);
        expect(filterRows(rows, null)).toBe(rows);
    });

    it('filters by level but always keeps level-less rows and gap markers', () => {
        const out = filterRows(rows, ['error']);
        expect(out.map((r) => r.seq)).toEqual([2, 3, 0]);
    });
});
