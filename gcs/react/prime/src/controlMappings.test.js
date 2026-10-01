import { describe, it, expect } from 'vitest';
import { CONTROL_MAPPINGS } from './controlMappings.js';

describe('CONTROL_MAPPINGS', () => {
  it('has exactly 12 rows', () => {
    expect(CONTROL_MAPPINGS).toHaveLength(12);
  });

  it('every row has a non-empty action', () => {
    CONTROL_MAPPINGS.forEach((row) => {
      expect(row.action).toBeTruthy();
    });
  });

  it('every row has at least one populated input mapping', () => {
    CONTROL_MAPPINGS.forEach((row) => {
      const hasKeyboard = row.keyboard && row.keyboard !== '—';
      const hasGamepad = row.gamepad && row.gamepad !== '—';
      expect(hasKeyboard || hasGamepad).toBe(true);
    });
  });

  it('actions are unique', () => {
    const actions = CONTROL_MAPPINGS.map((row) => row.action);
    expect(new Set(actions).size).toBe(actions.length);
  });

  it('includes the takeoff mapping matching App.jsx (KeyT / Y button 3)', () => {
    const takeoff = CONTROL_MAPPINGS.find((row) => row.action === 'Takeoff');
    expect(takeoff.keyboard).toBe('T');
    expect(takeoff.gamepad).toBe('Y / Triangle (3)');
  });

  it('includes the land mapping with both Xbox and PlayStation labels (KeyG / A/Cross button 0)', () => {
    const land = CONTROL_MAPPINGS.find((row) => row.action === 'Land');
    expect(land.keyboard).toBe('G');
    expect(land.gamepad).toBe('A / Cross (0)');
  });
});
