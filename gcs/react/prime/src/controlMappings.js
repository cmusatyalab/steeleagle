// Kept in sync manually with App.jsx's onKeyDown handler (~line 175) and the
// gamepad button/axis effects (~line 244, ~line 274). Update here if those
// bindings change.
export const CONTROL_MAPPINGS = [
  { action: 'Enable Manual / Hold', keyboard: 'Esc', gamepad: 'Start / Options (9)' },
  { action: 'Disable Manual Control', keyboard: '—', gamepad: 'Back/Select / Share (8)' },
  { action: 'Takeoff', keyboard: 'T', gamepad: 'Y / Triangle (3)' },
  { action: 'Land', keyboard: 'G', gamepad: 'A / Cross (0)' },
  { action: 'Return to Home', keyboard: 'Home', gamepad: 'LB / L1 (4)' },
  { action: 'Move Forward / Back', keyboard: 'W / S', gamepad: 'Right Stick Y (axis 3)' },
  { action: 'Move Left / Right', keyboard: 'A / D', gamepad: 'Right Stick X (axis 2)' },
  { action: 'Move Up / Down', keyboard: 'I / K', gamepad: 'Left Stick Y (axis 1)' },
  { action: 'Yaw Left / Right', keyboard: 'J / L', gamepad: 'Left Stick X (axis 0)' },
  { action: 'Stop (zero velocity)', keyboard: '0', gamepad: '—' },
  { action: 'Gimbal Pitch Up', keyboard: 'R', gamepad: 'D-Pad Up (12)' },
  { action: 'Gimbal Pitch Down', keyboard: 'F', gamepad: 'D-Pad Down (13)' },
];
