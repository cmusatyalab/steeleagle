import { describe, it, expect } from 'vitest';
import { runValidation } from './validation.js';

const schema = {
    actions: {
        Patrol: {
            fields: [
                { name: 'waypoints', required: true },
                { name: 'hover_time', required: false },
            ],
        },
        Wait: {
            fields: [
                { name: 'duration', required: true },
            ],
        },
    },
};

function makeNode(id, type_name, instance_id, params = {}) {
    return { id, data: { type_name, instance_id, params } };
}

describe('runValidation — required fields', () => {
    it('returns no issues when all required fields are set', () => {
        const nodes = [makeNode('n1', 'Patrol', 'p1', { waypoints: { alt: 15 } })];
        const { issues } = runValidation(nodes, schema, 'n1');
        expect(issues).toEqual({});
    });

    it('flags a missing required field', () => {
        const nodes = [makeNode('n1', 'Patrol', 'p1', {})];
        const { issues } = runValidation(nodes, schema, 'n1');
        expect(issues['n1']).toContain('waypoints is required');
    });

    it('flags null as missing', () => {
        const nodes = [makeNode('n1', 'Wait', 'w1', { duration: null })];
        const { issues } = runValidation(nodes, schema, 'n1');
        expect(issues['n1']).toContain('duration is required');
    });

    it('flags empty string as missing', () => {
        const nodes = [makeNode('n1', 'Wait', 'w1', { duration: '' })];
        const { issues } = runValidation(nodes, schema, 'n1');
        expect(issues['n1']).toContain('duration is required');
    });

    it('does not flag optional fields that are unset', () => {
        const nodes = [makeNode('n1', 'Patrol', 'p1', { waypoints: { alt: 15 } })];
        const { issues } = runValidation(nodes, schema, 'n1');
        expect(issues['n1']).toBeUndefined();
    });

    it('does not flag a node whose type is not in schema', () => {
        const nodes = [makeNode('n1', 'UnknownType', 'u1', {})];
        const { issues } = runValidation(nodes, schema, 'n1');
        expect(issues['n1']).toBeUndefined();
    });
});

describe('runValidation — duplicate instance IDs', () => {
    it('flags both nodes when instance_id is duplicated', () => {
        const nodes = [
            makeNode('n1', 'Patrol', 'patrol_1', { waypoints: {} }),
            makeNode('n2', 'Patrol', 'patrol_1', { waypoints: {} }),
        ];
        const { issues } = runValidation(nodes, schema, 'n1');
        expect(issues['n1']).toContain("Duplicate ID 'patrol_1'");
        expect(issues['n2']).toContain("Duplicate ID 'patrol_1'");
    });

    it('does not flag unique instance IDs', () => {
        const nodes = [
            makeNode('n1', 'Patrol', 'p1', { waypoints: {} }),
            makeNode('n2', 'Wait', 'w1', { duration: 5 }),
        ];
        const { issues } = runValidation(nodes, schema, 'n1');
        expect(issues['n1']).toBeUndefined();
        expect(issues['n2']).toBeUndefined();
    });
});

describe('runValidation — no start state', () => {
    it('sets noStart=true when startNodeId is null', () => {
        const { noStart } = runValidation([], schema, null);
        expect(noStart).toBe(true);
    });

    it('sets noStart=true when startNodeId is undefined', () => {
        const { noStart } = runValidation([], schema, undefined);
        expect(noStart).toBe(true);
    });

    it('sets noStart=false when startNodeId is set', () => {
        const nodes = [makeNode('n1', 'Wait', 'w1', { duration: 5 })];
        const { noStart } = runValidation(nodes, schema, 'n1');
        expect(noStart).toBe(false);
    });
});
