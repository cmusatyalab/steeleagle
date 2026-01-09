import React, { useState, useEffect, useRef } from "react";
import { useGamepad, BUTTON_LABELS, AXIS_LABELS } from "react-gamepad-tl";
import { Fieldset } from 'primereact/fieldset';
import { Toast } from 'primereact/toast';

function GameControls({ setAxis, setButton, deadzone }) {
  const [log, setLog] = useState([]);
  const gamePadToast = useRef(null);
  const { isGamepadConnected, gamepads, buttonStates, axisStates } = useGamepad(
    { deadzone: deadzone/100,
      pollInterval: 100
    }
  );
  //const AXIS_LABELS = { 0: 'Yaw', 1: 'Thrust', 2: 'Roll', 3: 'Pitch' } //Redefine these for our purpose
  // Update log when inputs change
  useEffect(() => {
    if (!isGamepadConnected) return;

    const messages = [];

    // Log button presses
    Object.entries(buttonStates).forEach(([padIndex, buttons]) => {
      setButton(buttons);
      Object.entries(buttons).forEach(([buttonIndex, state]) => {
        if (state.pressed) {
          const label = BUTTON_LABELS[buttonIndex] || `Button ${buttonIndex}`;
          messages.push(
            `${label} (${buttonIndex}) (${state.value.toFixed(2)})`
          );
        }
      });
    });

    // Log stick movements
    Object.entries(axisStates).forEach(([padIndex, axes]) => {
      setAxis(axes);
      Object.entries(axes).forEach(([axisIndex, value]) => {
        if (value !== 0) {
          const label = AXIS_LABELS[axisIndex] || `Axis ${axisIndex}`;
          messages.push(`${label} (${value.toFixed(2)})`);
          let a = {}
          a.index = axisIndex;
          a.value = value.toFixed(2);
        }
      });
    });

    if (messages.length > 0) {
      setLog((prev) => [...messages, ...prev].slice(0, 1));
    }
  }, [buttonStates, axisStates, isGamepadConnected]);

  useEffect(() => {
    if(Object.keys(gamepads).length > 0) {
      gamePadToast.current.replace({ severity: 'success', summary: 'Gamepad', detail: `Gamepad connected.`, sticky: true });
    }
    else {
      gamePadToast.current.replace({ severity: 'warn', summary: 'Gamepad', detail: 'No gamepad detected. Please connect a controller.', sticky: true });
    }
  }, [gamepads]);

  return (
    <>
      <Toast ref={gamePadToast} position="bottom-left"/>
    </>
  );
}

export default GameControls;
