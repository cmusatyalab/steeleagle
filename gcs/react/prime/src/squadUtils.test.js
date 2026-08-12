import { describe, it, expect } from 'vitest';
import { toggleVehicleInSquad, assignControlGroup, recallControlGroup, squadMatchesGroup, vehicleControlGroupDigits } from './squadUtils.js';

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

describe('squadMatchesGroup', () => {
    it('is true when the current squad exactly matches the group, same order', () => {
        expect(squadMatchesGroup(['a', 'b'], { '1': ['a', 'b'] }, '1')).toBe(true);
    });

    it('is true when the current squad matches the group in a different order', () => {
        expect(squadMatchesGroup(['b', 'a'], { '1': ['a', 'b'] }, '1')).toBe(true);
    });

    it('is false when the squad has an extra vehicle the group does not', () => {
        expect(squadMatchesGroup(['a', 'b', 'c'], { '1': ['a', 'b'] }, '1')).toBe(false);
    });

    it('is false when the squad is missing a vehicle the group has', () => {
        expect(squadMatchesGroup(['a'], { '1': ['a', 'b'] }, '1')).toBe(false);
    });

    it('is false when the group has never been assigned', () => {
        expect(squadMatchesGroup(['a'], {}, '1')).toBe(false);
    });

    it('treats a null squadList as empty', () => {
        expect(squadMatchesGroup(null, { '1': [] }, '1')).toBe(true);
    });

    it('treats an empty squad and a never-assigned (empty) group as matching sets -- callers gate the "unset" case separately via whether the group has any vehicles at all', () => {
        expect(squadMatchesGroup([], {}, '1')).toBe(true);
    });
});

describe('vehicleControlGroupDigits', () => {
    it('returns an empty array when the vehicle is in no group', () => {
        expect(vehicleControlGroupDigits({ '1': ['a'] }, 'b')).toEqual([]);
    });

    it('returns the one digit the vehicle belongs to', () => {
        expect(vehicleControlGroupDigits({ '1': ['a'], '2': ['b'] }, 'a')).toEqual(['1']);
    });

    it('returns every digit when the vehicle belongs to more than one group', () => {
        expect(vehicleControlGroupDigits({ '1': ['a'], '2': ['a'], '3': ['b'] }, 'a')).toEqual(['1', '2']);
    });

    it('returns [] for an empty controlGroups object', () => {
        expect(vehicleControlGroupDigits({}, 'a')).toEqual([]);
    });
});
