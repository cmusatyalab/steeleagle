import { useRef, useEffect, useState } from 'react'
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
import { FASTAPI_URL } from './config.js';
import { fetchEventSource } from "@microsoft/fetch-event-source";

function App() {
  const appName = "Talon";
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
  }, [useLocalVehicle]); // Empty dependency array means this runs once on mount

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
    setKeyPressed(true);
    if (e.code === 'Space') {
      setKey('space');

      return;
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
      onJoystick({ angularvel: 1.0, duration: 1 });
    }
    else if (e.code === 'KeyJ') {
      onJoystick({ angularvel: -1.0, duration: 1 });
    }
    else if (e.code === 'KeyI') {
      onJoystick({ zvel: 1.0, duration: 1 });
    }
    else if (e.code === 'KeyK') {
      onJoystick({ zvel: -1.0, duration: 1 });
    }
    //toast.current.show({ severity: 'success', summary: 'Key Pressed', detail: `'Pressed ${e.code}'` });
    setKey(e.key);

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
    if (gamePadButton == 3) {
      onCommand({ takeoff: true });
    }
    else if (gamePadButton == 0) {
      onCommand({ land: true });
    }
    else if (gamePadButton == 4) {
      onCommand({ rth: true });
    }
  }, [gamePadButton]);

  useEffect(() => {
    //pitch
    if (parseInt(gamePadAxis.index, 10) == 1) {
      onJoystick({ xvel: -1 * parseFloat(gamePadAxis.value), duration: 1 });
    }//yaw
    else if (parseInt(gamePadAxis.index, 10) == 0) {
      onJoystick({ angularvel: -1 * parseFloat(gamePadAxis.value), duration: 1 });
    }//thrust
    else if (parseInt(gamePadAxis.index, 10) == 3) {
      onJoystick({ zvel: -1 * parseFloat(gamePadAxis.value), duration: 1 });
    }//roll
    else if (parseInt(gamePadAxis.index, 10) == 2) {
      onJoystick({ yvel: parseFloat(gamePadAxis.value), duration: 1 });
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
      <ToggleButton onLabel="Tracking On" offLabel="Tracking Off" onIcon="pi pi-check" offIcon="pi pi-times"
        checked={tracking} onChange={(e) => setTracking(e.value)} />
      <Dropdown value={selectedVehicle} onChange={(e) => setSelectedVehicle(e.value)} options={vehicles} optionValue="name" optionLabel="name"
        placeholder="Select a Vehicle" className="w-full md:w-14rem" />
      <Button size="small" rounded text label="" icon="pi pi-question" onClick={() => setDebugBarVisible(true)} />
    </div>
  );

  return (
    <>
      <Menubar model={items} start={menuBarStart} end={menuBarEnd} />
      <Divider />
      {selectedMenu == "Control" && <ControlPage vehicles={vehicles} selectedVehicle={selectedVehicle} tracking={tracking} toast={toast} onCommand={onCommand} />}
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
