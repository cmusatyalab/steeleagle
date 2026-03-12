import { useRef, useEffect, useState, useCallback, useMemo } from 'react'
import useWebSocket, { ReadyState } from "react-use-websocket"
import './App.css'
import React from 'react'
import { Menubar } from 'primereact/menubar';
import { Divider } from 'primereact/divider';
import { Badge } from 'primereact/badge';
import { Button } from 'primereact/button';
import { Message } from 'primereact/message';
import { Toast } from 'primereact/toast';
import { Sidebar } from 'primereact/sidebar';
import { Dropdown } from 'primereact/dropdown';
import { DataTable } from 'primereact/datatable';
import { OverlayPanel } from 'primereact/overlaypanel';
import { ToggleButton } from 'primereact/togglebutton';
import { Knob } from 'primereact/knob';
import { Chip } from 'primereact/chip';
import 'primereact/resources/primereact.min.css';        // Core PrimeReact CSS
import 'primeicons/primeicons.css';                     // Icons
import 'primeflex/primeflex.css';                       // PrimeFlex utilities
import { classNames } from 'primereact/utils';
import { useEventListener } from 'primereact/hooks';
import GameControls from './GameControls.jsx'
import Cli from './Cli.jsx';
import ControlPage from './ControlPage.jsx';
import MonitorPage from './MonitorPage.jsx';
import PlanPage from './PlanPage.jsx';
import { FASTAPI_URL, WEBSOCKET_URL } from './config.js';
import { fetchEventSource } from "@microsoft/fetch-event-source";

const modeOptions = [
  { value: true, icon: 'pi pi-desktop' },
  { value: false, icon: 'pi pi-cloud' }
];

function App() {
  const appName = "SteelEagle";
  const [vehicles, setVehicles] = useState([]);
  const toast = useRef(null);
  const [selectedMenu, setSeletectedMenu] = useState('Control');
  const [keyPressed, setKeyPressed] = useState(false);
  const [key, setKey] = useState('');
  const [gamePadButton, setGamePadButton] = useState(-99);
  const [gamePadAxis, setGamePadAxis] = useState({ 'index': -99, 'value': -99 });
  const [selectedVehicle, setSelectedVehicle] = useState("");
  const [error, setError] = useState(null);
  const [tracking, setTracking] = useState(false);
  const [useLocalVehicle, setUseLocalVehicle] = useState(false);
  const [manualControl, setManualControl] = useState(false);
  const [basePlanarVelocity, setBasePlanarVelocity] = useState(1);
  const [baseAngularVelocity, setBaseAngularVelocity] = useState(45);
  const [takeOffAltitude, setTakeOffAltitude] = useState(3);
  const [showDetections, setShowDetections] = useState(true);
  const [gamepadDeadzone, setGamepadDeadzone] = useState(10);
  const [squadList, setSquadList] = useState(null);
  const [socketUrl, setSocketUrl] = useState('');
  const op = useRef(null);
  // Keep a ref to the last-known vehicles JSON so we can skip setVehicles when
  // the server returns identical data, preventing needless re-renders.
  const vehiclesJsonRef = useRef('');

  useEffect(() => {
    if (useLocalVehicle) {
      setSocketUrl(WEBSOCKET_URL + `/ws/imagery/${selectedVehicle}`);
    } else {
      setSocketUrl(WEBSOCKET_URL + `/ws/imagery/remote/${selectedVehicle}`);
    }
  }, [selectedVehicle, useLocalVehicle]);

  const { sendMessage, lastMessage, readyState } = useWebSocket(
    socketUrl,
    {
      share: false,
      shouldReconnect: () => true,
    },
  );

  // Run when the connection state (readyState) changes
  useEffect(() => {
    console.log(`Websocket state changed: ${readyState}`)
  }, [readyState]);

  // Run when a new WebSocket message is received (lastMessage)
  useEffect(() => {
    if (lastMessage != null) {
      var image = document.getElementById("image_stream");
      if (image != null) {
        image.src = "data:image/jpeg;base64," + lastMessage.data;
      }
    }
  }, [lastMessage]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        let response = "";
        if (!useLocalVehicle) {
          response = await fetch(`${FASTAPI_URL}/api/remote/vehicles`);
        }
        else {
          response = await fetch(`${FASTAPI_URL}/api/local/vehicles`);
        }
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const result = await response.json();
        // Only update state (and trigger a re-render) when the data has actually changed
        const resultJson = JSON.stringify(result);
        if (resultJson !== vehiclesJsonRef.current) {
          vehiclesJsonRef.current = resultJson;
          setVehicles(result);
        }
      } catch (error) {
        setError(error);
      }
    };

    fetchData();

    const intervalId = setInterval(fetchData, 500);
    return () => clearInterval(intervalId);
  }, [useLocalVehicle]);

  const onKeyDown = (e) => {
    if (e.code === 'Escape') {
      setManualControl(!manualControl);
    }
    if (manualControl) {
      setKeyPressed(true);
      if (e.code === 'Space') {
        onCommand({ hold: true });
      }
      else if (e.code === 'KeyT') {
        onCommand({ takeoff: takeOffAltitude });
      }
      else if (e.code === 'KeyG') {
        onCommand({ land: true });
      }
      else if (e.code === 'Home') {
        onCommand({ rth: true });
      }
      else if (e.code === 'KeyW') {
        onJoystick({ xvel: basePlanarVelocity, duration: 1 });
      }
      else if (e.code === 'KeyS') {
        onJoystick({ xvel: -1 * basePlanarVelocity, duration: 1 });
      }
      else if (e.code === 'KeyD') {
        onJoystick({ yvel: basePlanarVelocity, duration: 1 });
      }
      else if (e.code === 'KeyA') {
        onJoystick({ yvel: -1 * basePlanarVelocity, duration: 1 });
      }
      else if (e.code === 'KeyL') {
        onJoystick({ angularvel: baseAngularVelocity, duration: 1 });
      }
      else if (e.code === 'KeyJ') {
        onJoystick({ angularvel: -1 * baseAngularVelocity, duration: 1 });
      }
      else if (e.code === 'KeyI') {
        onJoystick({ zvel: basePlanarVelocity, duration: 1 });
      }
      else if (e.code === 'KeyK') {
        onJoystick({ zvel: -1 * basePlanarVelocity, duration: 1 });
      }
      else if (e.code === 'Digit0') {
        onJoystick({ zvel: 0, yvel: 0, xvel: 0, angularvel: 0, duration: 1 });
      }
      //toast.current.show({ severity: 'success', summary: 'Key Pressed', detail: `'Pressed ${e.code}'` });
      setKey(e.key);
    }
  };

  const [bindKeyDown, unbindKeyDown] = useEventListener({
    type: 'keydown',
    listener: (e) => {
      onKeyDown(e);
    }
  });

  const [bindKeyUp, unbindKeyUp] = useEventListener({
    type: 'keyup',
    listener: (e) => {
      setKeyPressed(false);
      //toast.current.show({ severity: 'info', summary: 'Key Released', detail: `Released ${e.code}. This is where we would make some GRPC call to hover.` });
    }
  });

  useEffect(() => {
    Object.entries(gamePadButton).forEach(([buttonIndex, state]) => {
      console.log(`Button ${buttonIndex}, Pressed: ${state.pressed}`);
      if (buttonIndex == 8 && state.pressed) {
        setManualControl(false);
      } else if (buttonIndex == 9 && state.pressed) {
        setManualControl(true);
      }
      if (manualControl) {
        if (buttonIndex == 3 && state.pressed) {
          onCommand({ takeoff: takeOffAltitude });
        }
        else if (buttonIndex == 0 && state.pressed) {
          onCommand({ land: true });
        }
        else if (buttonIndex == 4 && state.pressed) {
          onCommand({ rth: true });
        }

      }
    });
  }, [gamePadButton, takeOffAltitude]);

  useEffect(() => {
    let a = 0.0;
    let x = 0.0;
    let y = 0.0;
    let z = 0.0;

    if (manualControl) {
      Object.entries(gamePadAxis).forEach(([axisIndex, value]) => {
        console.log(`Axis ${axisIndex}, Value: ${value}`);
        if (value != 0.0) {
          if (axisIndex == 0) {
            a = value;
          }
          else if (axisIndex == 1) {
            z = value;
          }
          else if (axisIndex == 2) {
            y = value;
          }
          /*else if (axisIndex == 4) {
            y = value;
          }
          */
          else if (axisIndex == 3) {
            x = value;
          }
          /*else if (axisIndex == 5) {
            x = value;
          }
          */
        }
      });
      onJoystick({ xvel: -1 * basePlanarVelocity * x, yvel: basePlanarVelocity * y, zvel: -1 * basePlanarVelocity * z, angularvel: baseAngularVelocity * a, duration: 1 });

    }
  }, [gamePadAxis, manualControl]);

  useEffect(() => {
    if (selectedMenu == 'Control') {
      bindKeyDown();
      bindKeyUp();
    }
    return () => {
      unbindKeyDown();
      unbindKeyUp();
    };
  }, [bindKeyDown, bindKeyUp, unbindKeyDown, unbindKeyUp, selectedMenu]);

  const onJoystick = useCallback(async (body) => {
    body.vehicles = squadList;
    if (squadList == null || squadList.length == 0) {
      toast.current.show({ severity: 'warn', summary: 'No Vehicles in Squad', detail: `Please select at least one vehicle to control.` });
      return;
    } else {
      //toast.current.show({severity: 'info', summary: 'Joystick Sent', detail: `${JSON.stringify(body)}`});
      const requestOptions = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      };
      let response = null;
      if (useLocalVehicle) {
        response = await fetch(`${FASTAPI_URL}/api/joystick`, requestOptions);
      } else {
        response = await fetch(`${FASTAPI_URL}/api/joystick?sandbox_mode=0`, requestOptions);
      }
      if (!response.ok) {
        const result = await response.json();
        toast.current.show({ severity: 'error', summary: 'Joystick Error', detail: `HTTP error! status: ${result.detail}` });
      }
      else {
        const result = await response.json();
        // toast.current.show({severity: 'success', summary: 'Joystick Success', detail: `${result}`});

      }
    }
  }, [squadList, useLocalVehicle, basePlanarVelocity, baseAngularVelocity]);

  const onCommand = useCallback(async (body) => {
    body.vehicles = squadList;
    if (squadList == null || squadList.length == 0) {
      toast.current.show({ severity: 'warn', summary: 'No Vehicles in Squad', detail: `Please select at least one vehicle to control.` });
      return;
    } else {
      setManualControl(false);
      toast.current.show({ severity: 'info', summary: 'Command Sent', detail: `${JSON.stringify(body)}` });
      const requestOptions = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      };

      let response = null;
      if (useLocalVehicle) {
        response = await fetch(`${FASTAPI_URL}/api/command`, requestOptions);
      } else {
        response = await fetch(`${FASTAPI_URL}/api/command?sandbox_mode=0`, requestOptions);
      }
      if (!response.ok) {
        const result = await response.json();
        toast.current.show({ severity: 'error', summary: 'Command Error', detail: `HTTP error! status: ${result.detail}` });
      }
      else {
        const result = await response.json();
        toast.current.show({ severity: 'success', summary: 'Command Success', detail: `${result}` });
      }
    }

  }, [squadList, useLocalVehicle, takeOffAltitude]);

  const items = useMemo(() => [
    {
      label: 'Monitor',
      icon: 'pi pi-eye',
      command: () => {
        setSeletectedMenu('Monitor');
      },
    },
    {
      label: 'Control',
      icon: 'pi pi-sliders-v',
      command: () => {
        setSeletectedMenu('Control');
      },
    },
    {
      label: 'Plan',
      icon: 'pi pi-pencil',
      command: () => {
        setSeletectedMenu('Plan');
      },
    },

  ], []);

  const overlayContent = useMemo(() => (
    <>
      <div className="flex flex-row gap-2">
        <div className="flex flex-column flex-wrap align-content-center m-2">
          <ToggleButton onLabel="Use Local Vehicles (dev)" offLabel="Use Swarm Controller (prod)" onIcon="pi pi-desktop" offIcon="pi pi-cloud"
            checked={useLocalVehicle} onChange={(e) => setUseLocalVehicle(e.value)} className="flex align-items-center justify-content-center" />
        </div>
        <div className="flex flex-column flex-wrap align-content-center m-2">
        </div>
      </div>
      <div className="flex flex-row gap-2">
        <div className="flex flex-column flex-wrap align-content-center m-2">

        </div>
        <div className="flex flex-column flex-wrap justify-content-center align-content-center m-2">
        </div>
      </div>
    </>

  ), [useLocalVehicle, setUseLocalVehicle]);

  const menuBarStart = useMemo(() => (
    <div className="flex align-items-center gap-2 mr-2">
      <img alt="SteelEagle" src="logo.svg" height="40" className="flex align-items-center justify-content-center mr-2"></img>
      <h2 className="mt-3">{appName}</h2>
    </div>
  ), [appName]);

  const menuBarEnd = useMemo(() => (
    <div className="flex align-items-center gap-2 mr-2">
      <GameControls setAxis={setGamePadAxis} setButton={setGamePadButton} deadzone={gamepadDeadzone} />
      <Button size="small" rounded text label="" icon="pi pi-cog" onClick={(e) => op.current.toggle(e)} />
      <OverlayPanel ref={op}>{overlayContent}</OverlayPanel>

    </div>
  ), [useLocalVehicle, gamepadDeadzone, overlayContent]);


  const onToggleDetections = useCallback(async (value) => {
    setShowDetections(value);

    const requestOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        show_detections: value
      })
    };

    const response = await fetch(`${FASTAPI_URL}/api/imagery/show_detections`, requestOptions);

    if (!response.ok) {
      const result = await response.json();
      toast.current.show({
        severity: 'error',
        summary: 'Config Error',
        detail: `HTTP error! status: ${result.detail}`
      });
    } else {
      toast.current.show({
        severity: 'success',
        summary: 'Config Updated',
        detail: `Show detections set to ${value}`
      });
    }
  }, []);

  return (
    <>
      <Menubar model={items} start={menuBarStart} end={menuBarEnd} />
      <Divider />
      {selectedMenu == "Control" && <ControlPage vehicles={vehicles} selectedVehicle={selectedVehicle} setSelectedVehicle={setSelectedVehicle} tracking={tracking} setTracking={setTracking} toast={toast} onCommand={onCommand} useLocalVehicle={useLocalVehicle}
        manualControl={manualControl} setManualControl={setManualControl} squadList={squadList} setSquadList={setSquadList} basePlanarVelocity={basePlanarVelocity} setBasePlanarVelocity={setBasePlanarVelocity}
        baseAngularVelocity={baseAngularVelocity} setBaseAngularVelocity={setBaseAngularVelocity} gamepadDeadzone={gamepadDeadzone} setGamepadDeadzone={setGamepadDeadzone}
        takeOffAltitude={takeOffAltitude} setTakeOffAltitude={setTakeOffAltitude} showDetections={showDetections} onToggleDetections={onToggleDetections} />}
      {selectedMenu == "Monitor" && <MonitorPage vehicles={vehicles} />}
      {selectedMenu == "Plan" && <PlanPage />}
      <Toast ref={toast} />
    </>
  );
}

export default App;
