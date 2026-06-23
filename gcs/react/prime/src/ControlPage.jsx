import { useRef, useEffect, useState, useMemo } from 'react';
import { Knob } from 'primereact/knob';
import { Button } from 'primereact/button';
import { ToggleButton } from 'primereact/togglebutton';
import { Message } from 'primereact/message';
import { Chip } from 'primereact/chip';
import { OverlayPanel } from 'primereact/overlaypanel';
import { Panel } from 'primereact/panel';
import { Toolbar } from 'primereact/toolbar';
import { ButtonGroup } from 'primereact/buttongroup';
import { Tooltip } from 'primereact/tooltip';
import { FileUpload } from 'primereact/fileupload';
import { MultiSelect } from 'primereact/multiselect';
import { Dropdown } from 'primereact/dropdown';
import { Image } from 'primereact/image';
import React from 'react';
import { getApiUrl } from './App.jsx';
import Status from './Status.jsx';
import Mapbox from './Mapbox.jsx';

const cancelOptions = { icon: 'pi pi-fw pi-times', iconOnly: true, className: 'custom-cancel-btn p-button-danger' };
const chooseOptions = { label: 'Select...', icon: 'pi pi-fw pi-file', iconOnly: false, className: 'custom-choose-btn p-button-primary' };
const uploadOptions = { icon: 'pi pi-fw pi-cloud-upload', iconOnly: true, className: 'custom-upload-btn p-button-info' };

function ControlPage({ vehicles, selectedVehicle, setSelectedVehicle, tracking, setTracking, toast, onCommand, useLocalVehicle,
  manualControl, setManualControl, squadList, setSquadList, basePlanarVelocity, setBasePlanarVelocity,
  baseAngularVelocity, setBaseAngularVelocity, gamepadDeadzone, setGamepadDeadzone, takeOffAltitude, setTakeOffAltitude,
  showDetections, onToggleDetections, gimbalVelocity, setGimbalVelocity }) {
  const [mapPanelSize, setMapPanelSize] = useState(0);
  const [armed, setArmed] = useState(false);
  const op = useRef(null);
  const op2 = useRef(null);
  const onProgress = () => {
    toast.current.show({ severity: 'info', summary: 'In Progress', detail: 'Uploading files...' });
  };

  function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
  const uploadHandler = async (event) => {
    const body = {};
    body.vehicles = squadList;
    if (squadList == null || squadList.length == 0) {
      toast.current.show({ severity: 'warn', summary: 'No Vehicles in Squad', detail: `Please select at least one vehicle to control.` });
      return;
    } else {
      for (const file of event.files) {
        const reader = new FileReader();
        let blob = await fetch(file.objectURL).then((r) => r.blob()); //blob:url
        reader.readAsDataURL(blob);

        reader.onloadend = function () {
          const base64 = reader.result.split(',').pop();

          if (file.name.endsWith(".kml")) {
            body.kml = base64;
            console.log("Adding kml file");
          }
          else if (file.name.endsWith(".json")) {
            console.log("Adding json file");
            body.dsl = base64;
          }
        };

      }
      await sleep(2000);
      console.log(body);
      const requestOptions = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      };
      let response = null;
      if (useLocalVehicle) {
        response = await fetch(getApiUrl('/api/upload'), requestOptions);
      } else {
        response = await fetch(getApiUrl('/api/upload?sandbox_mode=0'), requestOptions);
      }
      if (!response.ok) {
        const result = await response.json();
        toast.current.show({ severity: 'error', summary: 'Upload Mission Error', detail: `HTTP error! status: ${result.detail}` });
      }
      else {
        const result = await response.json();
        toast.current.show({ severity: 'success', summary: 'Upload Mission', detail: `${result}` });
      }
    }

  };


  const onUploadComplete = () => {
    toast.current.show({ severity: 'success', summary: 'File Uploaded', detail: 'The mission has been uploaded.' });
  };

  const onMissionStart = async () => {
    const body = {};
    body.vehicles = squadList;
    if (squadList == null || squadList.length == 0) {
      toast.current.show({ severity: 'warn', summary: 'No Vehicles in Squad', detail: `Please select at least one vehicle to control.` });
      return;
    } else {
      setManualControl(false);
      const requestOptions = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      };
      let response = null;
      if (useLocalVehicle) {
        response = await fetch(getApiUrl('/api/start'), requestOptions);
      } else {
        response = await fetch(getApiUrl('/api/start?sandbox_mode=0'), requestOptions);
      }
      if (!response.ok) {
        const result = await response.json();
        toast.current.show({ severity: 'error', summary: 'Mission Error', detail: `HTTP error! status: ${result.detail}` });
      }
      else {
        const result = await response.json();
        toast.current.show({ severity: 'success', summary: 'Mission Success', detail: `${result}` });
      }
    }
  }

  const itemTemplate = (file) => (
    <span className="text-left ml-3">{file.name}</span>
  );

  const missonControls = useMemo(() => (
    <>
      <Tooltip target=".custom-choose-btn" content="Select Mission Files" position="bottom" />
      <Tooltip target=".custom-upload-btn" content="Upload Mission" position="bottom" />
      <Tooltip target=".custom-cancel-btn" content="Clear Selected Files" position="bottom" />
      <FileUpload className="m-2" itemTemplate={itemTemplate} chooseOptions={chooseOptions} uploadOptions={uploadOptions} cancelOptions={cancelOptions} mode="advanced" name="mission[]" url={'/api/upload'} multiple accept=".json,.kml,application/json,application/vnd.google-earth.kml+xml,text/xml,application/xml" maxFileSize={10000} customUpload uploadHandler={uploadHandler} onProgress={onProgress} onUpload={onUploadComplete} />
      <Button icon="pi pi-play-circle" label="Start Mission" className="m-2 p-button-success" onClick={onMissionStart} />
    </>
  ), [uploadHandler, onMissionStart]);

  const controlButtons = useMemo(() => (
    <>
      <div className="flex flex-column justify-content-end gap-1">
        <ButtonGroup className="w-full md:w-20rem flex align-content-center justify-content-center">
          <Button className="w-6" outlined size="small" icon="pi pi-check-circle" label="Arm" onClick={() => onCommand({ arm: true })} />
          <Button className="w-6" outlined size="small" iconPos="right" icon="pi pi-times-circle " label="Disarm" onClick={() => onCommand({ arm: false })} />
        </ButtonGroup>
        <ButtonGroup className="w-full md:w-20rem flex align-content-center justify-content-center">
          <Button className="w-6" outlined size="small" icon="pi pi-arrow-up" label="Takeoff" onClick={() => onCommand({ takeoff: takeOffAltitude })} />
          <Button className="w-6" outlined size="small" iconPos="right" icon="pi pi-arrow-down" label="Land" onClick={() => onCommand({ land: true })} />
        </ButtonGroup>
        <ButtonGroup className="w-full md:w-20rem flex align-content-center justify-content-center">
          <Button className="w-6" outlined size="small" icon="pi pi-home" label="RTH" onClick={() => onCommand({ rth: true })} />
          <Button className="w-6" outlined size="small" iconPos="right" icon="pi pi-stop-circle" label="Hold" onClick={() => onCommand({ hold: true })} />
        </ButtonGroup>
      </div>
    </>
  ), [onCommand]);

  const vehicleNames = useMemo(() => vehicles.map(v => v.name), [vehicles]);

  const squadComponent = useMemo(() => (
    <>
      <MultiSelect className="flex justify-content-center w-full md:w-20rem" value={squadList} onChange={(e) => setSquadList(e.value)} options={vehicleNames} useOptionAsValue display="chip"
        placeholder="Squad Selection" maxSelectedLabels={2} selectedItemsLabel="{0} vehicles selected." />
    </>
  ), [squadList, setSquadList, vehicleNames]);

  const overlayContent = useMemo(() => (
    <>
      <div className="flex flex-row gap-2">
        <div className="flex flex-column flex-wrap align-content-center m-2">
          <Knob className="flex align-items-center justify-content-center" value={basePlanarVelocity} onChange={(e) => setBasePlanarVelocity(e.value)} min={1} max={10} valueTemplate={'{value}m/s'} />
          <Chip className="flex align-items-center justify-content-center" label="Base Planar Velocity" icon="pi pi-sliders-v" />
        </div>
        <div className="flex flex-column flex-wrap align-content-center m-2">
          <Knob className="flex align-items-center justify-content-center" value={baseAngularVelocity} onChange={(e) => setBaseAngularVelocity(e.value)} min={15} max={180} step={15} valueTemplate={'{value}°/s'} />
          <Chip className="flex align-items-center justify-content-center" label="Base Angular Velocity" icon="pi pi-chart-pie" />
        </div>
        <div className="flex flex-column flex-wrap align-content-center m-2">
          <Knob className="flex align-items-center justify-content-center" value={gimbalVelocity} onChange={(e) => setGimbalVelocity(e.value)} min={5} max={45} step={5} valueTemplate={'{value}°/s'} />
          <Chip className="flex align-items-center justify-content-center" label="Gimbal Velocity" icon="pi pi-expand" />
        </div>
      </div>
      <div className="flex flex-row gap-2">
        <div className="flex flex-column flex-wrap align-content-center m-2">
          <Knob className="flex align-items-center justify-content-center" value={gamepadDeadzone} onChange={(e) => setGamepadDeadzone(e.value)} min={5} max={50} step={5} valueTemplate={'{value}%'} />
          <Chip className="flex align-items-center justify-content-center" label="Gamepad Deadzone" icon="pi pi-bullseye" />
        </div>
        <div className="flex flex-column flex-wrap align-content-center m-2">
          <Knob className="flex align-items-center justify-content-center" value={takeOffAltitude} onChange={(e) => setTakeOffAltitude(e.value)} min={1} max={10} step={1} valueTemplate={'{value}m'} />
          <Chip className="flex align-items-center justify-content-center" label="Takeoff Altitude" icon="pi pi-sort-numeric-up-alt" />
        </div>
      </div>
      <div className="flex flex-row gap-2">
        <div className="flex flex-column flex-wrap justify-content-center align-content-center m-2">
          <ToggleButton onLabel="Tracking On" offLabel="Tracking Off" onIcon="pi pi-bullseye" offIcon="pi pi-map"
            checked={tracking} onChange={(e) => setTracking(e.value)} className="flex" tooltip="When enabled, the map will recenter on the selected vehicle." />
        </div>
        <div className="flex flex-column flex-wrap justify-content-center align-content-center m-2">
          <ToggleButton onLabel="Show Detections" offLabel="Hide Detections" onIcon="pi pi-expand" offIcon="pi pi-expand"
            checked={showDetections} onChange={(e) => onToggleDetections(e.value)} className="flex" tooltip="When enabled, the video stream will show detection bounding boxes." />
        </div>


      </div>
    </>

  ), [baseAngularVelocity, setBaseAngularVelocity, basePlanarVelocity, setBasePlanarVelocity,
    gamepadDeadzone, setGamepadDeadzone, tracking, setTracking, takeOffAltitude, setTakeOffAltitude,
    showDetections, onToggleDetections, gimbalVelocity, setGimbalVelocity]);

  const swarmHeaderTemplate = (options) => {
    const className = `${options.className} justify-content-space-between`;

    return (
      <div className={className}>
        <div className="flex align-items-center gap-2">
          <span className="font-bold">Swarm Controls</span>
        </div>
        <div className="flex align-items-center gap-2" >
          {manualControl && <Message severity="success" text="Manual Control Enabled" />}
          {!manualControl && <Message severity="error" text="Manual Control Disabled" />}
          {squadComponent}
          <Button size="small" rounded text label="" icon="pi pi-cog" onClick={(e) => op2.current.toggle(e)} />
          <OverlayPanel ref={op2}><span>Swarm Settings</span></OverlayPanel>
          {options.togglerElement}
        </div>
      </div>
    );
  };
  const headerTemplate = (options) => {
    const className = `${options.className} justify-content-space-between`;

    return (
      <div className={className}>
        <div className="flex align-items-center gap-2">
          <span className="font-bold">Vehicle Details</span>
        </div>
        <div className="flex align-items-center gap-2">
          <Dropdown value={selectedVehicle} checkmark={true} onChange={(e) => setSelectedVehicle(e.value)} options={vehicleNames} useOptionAsValue optionLabel="name"
            placeholder="Select a Vehicle" className="w-full md:w-14rem" />
          <Button size="small" rounded text label="" icon="pi pi-cog" onClick={(e) => op.current.toggle(e)} />
          <OverlayPanel ref={op}>{overlayContent}</OverlayPanel>
          {options.togglerElement}
        </div>
      </div>
    );
  };

  const selectedVehicleData = useMemo(
    () => vehicles.find(v => v.name === selectedVehicle),
    [vehicles, selectedVehicle]
  );

  return (
    <>
      <div className="flex flex-column">
        <Panel headerTemplate={headerTemplate} className="h-full" >
          <div className="grid m-0">
            <div className="col-12 lg:col-5 p-2">
              <Mapbox selectedVehicle={selectedVehicle} vehicles={vehicles} mapPanelSize={mapPanelSize} tracking={tracking} />
            </div>
            <div className="col-12 lg:col-4 p-2">
              <Image height="100%" width="100%" pt={{ image: { id: 'image_stream' } }} src="nostream.png" />
            </div>
            <div className="col-12 lg:col-3 p-2">
              <Status vehicle={selectedVehicleData} />
            </div>
          </div>
        </Panel>
        <Panel headerTemplate={swarmHeaderTemplate} className="my-2 h-full">
          <Toolbar className="w-full" start={controlButtons} end={missonControls} />
        </Panel>
      </div>
    </>
  );
}

export default React.memo(ControlPage);
