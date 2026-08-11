import { describe, it, expect } from 'vitest';
import { toggleVehicleInSquad, assignControlGroup, recallControlGroup } from './squadUtils.js';

describe('toggleVehicleInSquad', () => {
    it('adds a name not present', () => {
        expect(toggleVehicleInSquad(['a'], 'b')).toEqual(['a', 'b']);
    });

    it('removes a name that is present', () => {
        expect(toggleVehicleInSquad(['a', 'b'], 'a')).toEqual(['b']);
    });

    it('treats null squadList as empty and adds to a fresh array', () => {
        expect(toggleVehicleInSquad(null, 'a')).toEqual(['a']);
    });

    it('treats undefined squadList as empty and adds to a fresh array', () => {
        expect(toggleVehicleInSquad(undefined, 'a')).toEqual(['a']);
    });

    it('does not mutate the input array', () => {
        const input = ['a'];
        toggleVehicleInSquad(input, 'b');
        expect(input).toEqual(['a']);
    });
});

describe('assignControlGroup', () => {
    it('assigns a squad into an unset slot', () => {
        expect(assignControlGroup({}, '1', ['a', 'b'])).toEqual({ '1': ['a', 'b'] });
    });

    it('overwrites an already-occupied slot', () => {
        expect(assignControlGroup({ '1': ['a'] }, '1', ['b', 'c'])).toEqual({ '1': ['b', 'c'] });
    });

    it('treats null squadList as an empty array in the stored snapshot', () => {
        expect(assignControlGroup({}, '1', null)).toEqual({ '1': [] });
    });

    it('treats undefined squadList as an empty array in the stored snapshot', () => {
        expect(assignControlGroup({}, '1', undefined)).toEqual({ '1': [] });
    });

    it('does not mutate the input controlGroups object', () => {
        const input = { '1': ['a'] };
        assignControlGroup(input, '1', ['b']);
        expect(input).toEqual({ '1': ['a'] });
    });
});

describe('recallControlGroup', () => {
    it('recalling a populated slot returns that slot\'s array', () => {
        expect(recallControlGroup({ '1': ['a', 'b'] }, '1')).toEqual(['a', 'b']);
    });

    it('recalling a never-assigned slot returns [] rather than undefined', () => {
        expect(recallControlGroup({}, '1')).toEqual([]);
    });
});
