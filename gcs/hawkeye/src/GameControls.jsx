import React, { useState, useEffect } from "react";
import { useGamepad, BUTTON_LABELS, AXIS_LABELS } from "react-gamepad-tl";
import Accordion from 'react-bootstrap/Accordion';

function GameControls() {
const [log, setLog] = useState([]);
  const { isGamepadConnected, gamepads, buttonStates, axisStates } = useGamepad(
    { deadzone: 0.1 }
  );
  const AXIS_LABELS = {0: 'Yaw', 1: 'Thrust', 2: 'Roll', 3: 'Pitch'} //Redefine these for our purpose
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
      setLog((prev) => [...messages, ...prev].slice(0, 10));
    }
  }, [buttonStates, axisStates, isGamepadConnected]);

  return (
    <>
     <Accordion data-bs-theme="dark">
      <Accordion.Item eventKey="0">
        <Accordion.Header>Gamepad Status</Accordion.Header>
        <Accordion.Body>
         {!isGamepadConnected ? (
        <div>No gamepad detected. Please connect a controller.</div>
      ) : (
        <div>
          {Object.values(gamepads).map((gamepad) => (
            <div key={gamepad.index}>
              {gamepad.id} (Index: {gamepad.index})
            </div>
          ))}

        {log.map((message, index) => (
          <div key={index}>{message}</div>
        ))}
        </div>
      )}
        </Accordion.Body>
      </Accordion.Item>
      </Accordion>
      </>
  );
}

export default GameControls;
