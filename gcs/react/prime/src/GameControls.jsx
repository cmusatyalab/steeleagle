import React, { useState, useEffect } from "react";
import { useGamepad, BUTTON_LABELS, AXIS_LABELS } from "react-gamepad-tl";
import { Fieldset } from 'primereact/fieldset';
import { Divider } from 'primereact/divider';

function GameControls() {
  const [log, setLog] = useState([]);
  const { isGamepadConnected, gamepads, buttonStates, axisStates } = useGamepad(
    { deadzone: 0.1 }
  );
  //const AXIS_LABELS = { 0: 'Yaw', 1: 'Thrust', 2: 'Roll', 3: 'Pitch' } //Redefine these for our purpose
  // Update log when inputs change
  useEffect(() => {
    if (!isGamepadConnected) return;

    const messages = [];

    // Log button presses
    Object.entries(buttonStates).forEach(([padIndex, buttons]) => {
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
      Object.entries(axes).forEach(([axisIndex, value]) => {
        if (value !== 0) {
          const label = AXIS_LABELS[axisIndex] || `Axis ${axisIndex}`;
          messages.push(`${label} (${value.toFixed(2)})`);
        }
      });
    });

    if (messages.length > 0) {
      setLog((prev) => [...messages, ...prev].slice(0, 1));
    }
  }, [buttonStates, axisStates, isGamepadConnected]);


  /*
                {Object.values(gamepads).map((gamepad) => (
                <div key={gamepad.index}>
                  {gamepad.id}
                </div>
              ))}
              <Divider />
  */
  return (
    <>
          {!isGamepadConnected ? (
            <p>No gamepad detected. Please connect a controller.</p>
          ) : (
            <>
              {log.map((message, index) => (
                <p key={index}>{message}</p>
              ))}
            </>
          )}
    </>
  );
}

export default GameControls;
