import { useRef, useEffect, useState } from 'react'
import useWebSocket, { ReadyState } from "react-use-websocket"
import './App.css'
import React from 'react'
import { Menubar } from 'primereact/menubar';
import { Divider } from 'primereact/divider';
import { Badge } from 'primereact/badge';
import { Button } from 'primereact/button';
import { ToggleButton } from 'primereact/togglebutton';
import { Toast } from 'primereact/toast';
import { Sidebar } from 'primereact/sidebar';
import { Dropdown } from 'primereact/dropdown';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { MultiStateCheckbox } from 'primereact/multistatecheckbox';
import { FloatLabel } from 'primereact/floatlabel';
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

function App() {
  const appName = "SteelEagle";
  const [vehicles, setVehicles] = useState([]);
  const toast = useRef(null);
  const [debugBarVisible, setDebugBarVisible] = useState(false);
  const [selectedMenu, setSeletectedMenu] = useState('Control');
  const [keyPressed, setKeyPressed] = useState(false);
  const [key, setKey] = useState('');
  const [gamePadButton, setGamePadButton] = useState(-99);
  const [gamePadAxis, setGamePadAxis] = useState({ 'index': -99, 'value': -99 });
  const [selectedVehicle, setSelectedVehicle] = useState("");
  const [error, setError] = useState(null);
  const [tracking, setTracking] = useState(false);
  const [useLocalVehicle, setUseLocalVehicle] = useState(true);
  const [manualControl, setManualControl] = useState(true);

  const controlOptions = [
    { value: true, icon: 'pi pi-lock-open' },
    { value: false, icon: 'pi pi-lock' }
  ];

  const trackingOptions = [
    { value: true, icon: 'pi pi-bullseye' },
    { value: false, icon: 'pi pi-map' }
  ];

  const { sendMessage, lastMessage, readyState } = useWebSocket(
    WEBSOCKET_URL + '/ws',
    {
      share: false,
      shouldReconnect: () => true,
    },
  );

  // Run when the connection state (readyState) changes
  useEffect(() => {
    console.log("Connection state changed")
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
      if (!useLocalVehicle) {
        try {
          const response = await fetch(`${FASTAPI_URL}/api/vehicles`);
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
          const result = await response.json();
          setVehicles(result);
        } catch (error) {
          setError(error);
        }
      }
    };

    fetchData();

    const intervalId = setInterval(fetchData, 1000);
    return () => clearInterval(intervalId);
  }, [useLocalVehicle]);

  useEffect(() => {
    const controller = new AbortController();
    const sse = async () => {
      if (useLocalVehicle) {
        await fetchEventSource(`${FASTAPI_URL}/api/local/vehicle`, {
          signal: controller.signal,
          onmessage(ev) {
            if (ev.event == "driver_telemetry") {
              const v = [];
              console.log(ev.data);
              try {
                v.push(JSON.parse(ev.data));
              }
              catch (error) {
                console.log(error);
              }
              setVehicles(v);
            }
          },
        });
      };
    }
    sse();
    return () => {
      controller.abort();
    };

  }, [useLocalVehicle]);

  const onKeyDown = (e) => {
    if (manualControl) {
      setKeyPressed(true);
      if (e.code === 'Space') {
        onCommand({ hold: true });
      }
      else if (e.code === 'KeyT') {
        onCommand({ takeoff: true });
      }
      else if (e.code === 'KeyG') {
        onCommand({ land: true });
      }
      else if (e.code === 'Home') {
        onCommand({ rth: true });
      }
      else if (e.code === 'KeyW') {
        onJoystick({ xvel: 1.0, duration: 1 });
      }
      else if (e.code === 'KeyS') {
        onJoystick({ xvel: -1.0, duration: 1 });
      }
      else if (e.code === 'KeyD') {
        onJoystick({ yvel: 1.0, duration: 1 });
      }
      else if (e.code === 'KeyA') {
        onJoystick({ yvel: -1.0, duration: 1 });
      }
      else if (e.code === 'KeyL') {
        onJoystick({ angularvel: 20.0, duration: 1 });
      }
      else if (e.code === 'KeyJ') {
        onJoystick({ angularvel: -20.0, duration: 1 });
      }
      else if (e.code === 'KeyI') {
        onJoystick({ zvel: 1.0, duration: 1 });
      }
      else if (e.code === 'KeyK') {
        onJoystick({ zvel: -1.0, duration: 1 });
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
    if (manualControl) {
      Object.entries(gamePadButton).forEach(([buttonIndex, state]) => {
        console.log(`Index: ${buttonIndex}, Pressed: ${state.pressed}, Touched: ${state.touched}`);
        if (buttonIndex == 3 && state.pressed) {
          onCommand({ takeoff: true });
        }
        else if (buttonIndex == 0 && state.pressed) {
          onCommand({ land: true });
        }
        else if (buttonIndex == 4 && state.pressed) {
          onCommand({ rth: true });
        }
      });
    }
  }, [gamePadButton]);

  useEffect(() => {
    let max_planar_vel = 5.0;
    let a = 0.0;
    let x = 0.0;
    let y = 0.0;
    let z = 0.0;

    if (manualControl) {
      Object.entries(gamePadAxis).forEach(([axisIndex, value]) => {
        if (axisIndex == 0) {
          a = value;
        }
        else if (axisIndex == 1) {
          z = value;
        }
        else if (axisIndex == 2 || axisIndex == 4) {
          y = value;
        }
        else if (axisIndex == 3 || axisIndex == 5) {
          x = value;
        }
      });
      onJoystick({ xvel: -1 * max_planar_vel * x, yvel: max_planar_vel * y, zvel: -1 * max_planar_vel * z, angularvel: 20 * a, duration: 1 });
    }
  }, [gamePadAxis]);

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

  const onJoystick = async (body) => {
    //toast.current.show({severity: 'info', summary: 'Joystick Sent', detail: `${JSON.stringify(body)}`});
    const requestOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    };
    const response = await fetch(`${FASTAPI_URL}/api/joystick`, requestOptions);
    if (!response.ok) {
      const result = await response.json();
      toast.current.show({ severity: 'error', summary: 'Joystick Error', detail: `HTTP error! status: ${result.detail}` });
    }
    else {
      const result = await response.json();
      // toast.current.show({severity: 'success', summary: 'Joystick Success', detail: `${result}`});

    }

  }

  const onCommand = async (body) => {
    //toast.current.show({ severity: 'info', summary: 'Command Sent', detail: `${JSON.stringify(body)}` });
    const requestOptions = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    };
    const response = await fetch(`${FASTAPI_URL}/api/command`, requestOptions);
    if (!response.ok) {
      const result = await response.json();
      toast.current.show({ severity: 'error', summary: 'Command Error', detail: `HTTP error! status: ${result.detail}` });
    }
    else {
      const result = await response.json();
      toast.current.show({ severity: 'success', summary: 'Command Success', detail: `${result}` });

    }

  }

  const itemRenderer = (item) => (
    <a className="flex align-items-center p-menuitem-link">
      <span className={item.icon}></span>
      <span className="mx-2 p-overlay-badge">{item.label}</span>
      {item.label == selectedMenu && <Badge className="mr-2" severity="info" />}
      {item.shortcut && <span className="ml-auto border-1 surface-border border-round surface-100 text-xs p-1">{item.shortcut}</span>}
    </a>
  );
  const items = [
    {
      label: 'Monitor',
      icon: 'pi pi-eye',
      command: () => {
        setSeletectedMenu('Monitor');
      },
      template: itemRenderer,
    },
    {
      label: 'Control',
      icon: 'pi pi-sliders-v',
      command: () => {
        setSeletectedMenu('Control');
      },
      template: itemRenderer,
    },
    {
      label: 'Plan',
      icon: 'pi pi-pencil',
      command: () => {
        setSeletectedMenu('Plan');
      },
      template: itemRenderer,
    },

  ];



  const menuBarStart = <div className="flex align-items-center gap-2"><img alt="SteelEagle" src="logo.svg" height="40" className="flex align-items-center justify-content-center mr-2"></img><h2 className="mt-3">{appName}</h2></div>;
  const menuBarEnd = (
    <div className="flex align-items-center gap-2">
      <GameControls setAxis={setGamePadAxis} setButton={setGamePadButton} />
      <MultiStateCheckbox tooltip={manualControl ? "Manual Control: Enabled" : "Manual Control: Disabled"} data-pr-position="bottom" empty={false} value={manualControl} onChange={(e) => setManualControl(e.value)} options={controlOptions} optionValue="value" />
      <MultiStateCheckbox tooltip={tracking ? "Vehicle Tracking: On" : "Vehicle Tracking: Off"} data-pr-position="bottom" empty={false} value={tracking} onChange={(e) => setTracking(e.value)} options={trackingOptions} optionValue="value" />
      <Dropdown value={selectedVehicle} onChange={(e) => setSelectedVehicle(e.value)} options={vehicles} optionValue="name" optionLabel="name"
        placeholder="Select a Vehicle" className="w-full md:w-14rem" />
      <Button size="small" rounded text label="" icon="pi pi-question" onClick={() => setDebugBarVisible(true)} />
    </div>
  );

  return (
    <>
      <Menubar model={items} start={menuBarStart} end={menuBarEnd} />
      <Divider />
      {selectedMenu == "Control" && <ControlPage vehicles={vehicles} selectedVehicle={selectedVehicle} tracking={tracking} toast={toast} onCommand={onCommand} useLocalVehicle={useLocalVehicle} />}
      {selectedMenu == "Monitor" && <MonitorPage vehicles={vehicles} />}
      {selectedMenu == "Plan" && <PlanPage />}
      <Sidebar visible={debugBarVisible} position="right" onHide={() => setDebugBarVisible(false)} style={{ width: "50%" }}>
        <h2>Debug</h2>
        <div className="card flex flex-column align-items-center">
          <ToggleButton className="m-2" onLabel="Use Local Vehicle" offLabel="Use Swarm Controller" onIcon="pi pi-desktop" offIcon="pi pi-cloud"
            checked={useLocalVehicle} onChange={(e) => setUseLocalVehicle(e.value)} />
          <button
            className={classNames('card border-1 surface-border border-round-sm py-3 px-4 text-color font-semibold text-sm transition-all transition-duration-150', { 'shadow-1': keyPressed, 'shadow-5': !keyPressed })}
            style={{
              background: '-webkit-linear-gradient(top, var(--surface-ground) 0%, var(--surface-card) 100%)',
              transform: keyPressed ? 'translateY(5px)' : 'translateY(0)'
            }}>
            {key.toUpperCase() || 'Press a Key'}
          </button>
          <div style={{ width: "100%" }} className="card">
            <DataTable value={vehicles} scrollable stripedRows size="small">
              <Column field="name" frozen sortable header="Name"></Column>
              <Column field="type" sortable header="Type"></Column>
              <Column field="model" sortable header="Model"></Column>
              <Column field="battery" header="Battery Alert"></Column>
              <Column field="mag" header="Mag Alert"></Column>
              <Column field="sats" header="Sats Alert"></Column>
              <Column field="current.lat" header="Current (Lat)"></Column>
              <Column field="current.long" header="Current (Lon)"></Column>
              <Column field="current.alt" header="Current (Alt)"></Column>
              <Column field="home.lat" header="Home (Lat)"></Column>
              <Column field="home.long" header="Home (Lon)"></Column>
              <Column field="home.alt" header="Home (Alt)"></Column>
            </DataTable>
          </div>
          <Button icon="pi pi-arrow-up" className="m-2" label="Takeoff" onClick={() => onCommand({ takeoff: true })} />
          <Button icon="pi pi-arrow-down" className="m-2" label="Land" onClick={() => onCommand({ land: true })} />
          <Cli vehicle={selectedVehicle} />
        </div>
      </Sidebar>

      <Toast ref={toast} />
    </>
  );
}

export default App;
