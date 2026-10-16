import { describe, it, expect } from 'vitest';
import { fromRows, newRow, retype, toRows, typeOf } from './kvArgs.js';

describe('toRows / fromRows', () => {
    it('round-trips scalars with types', () => {
        const rows = toRows({ model: 'yolov8n', confidence: 0.5, enabled: true });
        expect(rows.map((r) => [r.key, r.type, r.value])).toEqual([
            ['model', 'string', 'yolov8n'],
            ['confidence', 'number', '0.5'],
            ['enabled', 'boolean', true],
        ]);
        expect(fromRows(rows)).toEqual({ value: { model: 'yolov8n', confidence: 0.5, enabled: true }, errors: {} });
    });

    it('passes arrays and tables through untouched as read-only rows', () => {
        const rows = toRows({ modes: ['a', 'b'], nested: { x: 1 } });
        expect(rows.map((r) => r.type)).toEqual(['other', 'other']);
        expect(fromRows(rows).value).toEqual({ modes: ['a', 'b'], nested: { x: 1 } });
    });

    it('treats a missing object as no rows', () => {
        expect(toRows(undefined)).toEqual([]);
    });

    it('reports empty keys, duplicate keys, and bad numbers per row', () => {
        const rows = [
            { ...newRow(), key: '' },
            { ...newRow(), key: 'a', value: 'x' },
            { ...newRow(), key: 'a', value: 'y' },
            { ...newRow(), key: 'n', type: 'number', value: 'abc' },
            { ...newRow(), key: 'm', type: 'number', value: ' ' },
        ];
        const { value, errors } = fromRows(rows);
        expect(value).toEqual({ a: 'x' });
        expect(Object.values(errors)).toEqual(['Key is required', 'Duplicate key "a"', 'Not a number', 'Not a number']);
    });

    it('trims keys', () => {
        expect(fromRows([{ ...newRow(), key: ' k ', value: 'v' }]).value).toEqual({ k: 'v' });
    });
});

describe('retype', () => {
    it('converts values between types', () => {
        const row = { ...newRow(), key: 'k', value: 'true' };
        expect(retype(row, 'boolean').value).toBe(true);
        expect(retype({ ...row, type: 'boolean', value: false }, 'number').value).toBe('0');
        expect(retype({ ...row, type: 'number', value: '3' }, 'string').value).toBe('3');
    });
});

describe('typeOf', () => {
    it('classifies values', () => {
        expect([typeOf('s'), typeOf(1), typeOf(false), typeOf([]), typeOf(null)]).toEqual(['string', 'number', 'boolean', 'other', 'other']);
    });
});
