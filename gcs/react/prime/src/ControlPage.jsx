import { useRef, useState, useMemo, useCallback } from 'react';
import { Button } from 'primereact/button';
import { Message } from 'primereact/message';
import { Chip } from 'primereact/chip';
import { OverlayPanel } from 'primereact/overlaypanel';
import { Panel } from 'primereact/panel';
import { Toolbar } from 'primereact/toolbar';
import { ButtonGroup } from 'primereact/buttongroup';
import { Tooltip } from 'primereact/tooltip';
import { FileUpload } from 'primereact/fileupload';
import { Image } from 'primereact/image';
import React from 'react';
import { getApiUrl } from './urls.js';
import VehicleGrid from './VehicleGrid.jsx';
import Mapbox from './Mapbox.jsx';
import { toggleVehicleInSquad, recallControlGroup } from './squadUtils.js';

const cancelOptions = { icon: 'pi pi-fw pi-times', iconOnly: true, className: 'custom-cancel-btn p-button-danger' };
const chooseOptions = { label: 'Select...', icon: 'pi pi-fw pi-file', iconOnly: false, className: 'custom-choose-btn p-button-primary' };
const uploadOptions = { icon: 'pi pi-fw pi-cloud-upload', iconOnly: true, className: 'custom-upload-btn p-button-info' };
const controlGroupDigits = ['1', '2', '3', '4', '5', '6', '7', '8', '9'];

function ControlPage({ vehicles, selectedVehicle, tracking, toast, onCommand,
  manualControl, setManualControl, squadList, setSquadList, takeOffAltitude, controlGroups }) {
  const [mapPanelSize] = useState(0);
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
      const response = await fetch(getApiUrl('/api/upload'), requestOptions);
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
      const response = await fetch(getApiUrl('/api/start'), requestOptions);
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
  ), [uploadHandler, onMissionStart, onProgress, onUploadComplete]);

  const controlButtons = useMemo(() => (
    <div className="flex flex-row flex-wrap gap-2">
      <ButtonGroup>
        <Button outlined size="small" icon="pi pi-check-circle" label="Arm" onClick={() => onCommand({ arm: true })} />
        <Button outlined size="small" iconPos="right" icon="pi pi-times-circle" label="Disarm" onClick={() => onCommand({ arm: false })} />
      </ButtonGroup>
      <ButtonGroup>
        <Button outlined size="small" icon="pi pi-arrow-up" label="Takeoff" onClick={() => onCommand({ takeoff: takeOffAltitude })} />
        <Button outlined size="small" iconPos="right" icon="pi pi-arrow-down" label="Land" onClick={() => onCommand({ land: true })} />
      </ButtonGroup>
      <ButtonGroup>
        <Button outlined size="small" icon="pi pi-home" label="RTH" onClick={() => onCommand({ rth: true })} />
        <Button outlined size="small" iconPos="right" icon="pi pi-stop-circle" label="Hold" onClick={() => onCommand({ hold: true })} />
      </ButtonGroup>
    </div>
  ), [onCommand, takeOffAltitude]);

  const vehicleNames = useMemo(() => vehicles.map(v => v.name), [vehicles]);

  const onSelectAllSquad = useCallback(() => setSquadList([...vehicleNames]), [vehicleNames, setSquadList]);
  const onClearSquad = useCallback(() => setSquadList([]), [setSquadList]);
  const onRecallGroup = useCallback((digit) => setSquadList(recallControlGroup(controlGroups, digit)), [controlGroups, setSquadList]);

  const swarmCenterContent = useMemo(() => (
    <div className="flex flex-row align-items-center gap-2 flex-wrap justify-content-center">
      <Chip label={(squadList ?? []).length === 1 ? '1 vehicle selected' : `${(squadList ?? []).length} vehicles selected`} icon="pi pi-users" />
      <Button size="small" text label="Select All" icon="pi pi-check-square" onClick={onSelectAllSquad} />
      <Button size="small" text label="Clear" icon="pi pi-times" onClick={onClearSquad} />
      <ButtonGroup>
        {controlGroupDigits.map((digit) => (
          <Button
            key={digit}
            size="small"
            outlined={!(controlGroups[digit]?.length > 0)}
            label={digit}
            tooltip={`Group ${digit}: ${(controlGroups[digit] ?? []).length} vehicles`}
            tooltipOptions={{ position: 'bottom' }}
            onClick={() => onRecallGroup(digit)}
          />
        ))}
      </ButtonGroup>
    </div>
  ), [squadList, controlGroups, onSelectAllSquad, onClearSquad, onRecallGroup]);

  const onToggleVehicle = (name) => setSquadList((prev) => toggleVehicleInSquad(prev, name));

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
          <Button size="small" rounded text label="" icon="pi pi-cog" onClick={(e) => op2.current.toggle(e)} />
          <OverlayPanel ref={op2}><span>Swarm Settings</span></OverlayPanel>
          {options.togglerElement}
        </div>
      </div>
    );
  };

  return (
    <>
      <div className="grid m-0">
        <div className="col-12 lg:col-3 p-2">
          <Panel header="Squad" className="h-full">
            <div className="grid m-0" style={{ maxHeight: 'calc(100vh - 220px)', overflowY: 'auto' }}>
              <VehicleGrid vehicles={vehicles} selectable squadList={squadList} onToggle={onToggleVehicle} cardColumnClass="col-12 p-2" />
            </div>
          </Panel>
        </div>
        <div className="col-12 lg:col-9 p-2">
          <div className="flex flex-column">
            <div className="grid m-0">
              <div className="col-12 lg:col-6 p-2">
                <Mapbox selectedVehicle={selectedVehicle} vehicles={vehicles} mapPanelSize={mapPanelSize} tracking={tracking}
                  squadList={squadList} onToggleVehicle={onToggleVehicle} />
              </div>
              <div className="col-12 lg:col-6 p-2">
                <Image height="100%" width="100%" pt={{ image: { id: 'image_stream' } }} src="nostream.png" />
              </div>
            </div>
            <Panel headerTemplate={swarmHeaderTemplate} className="my-2 h-full">
              <Toolbar className="w-full" start={controlButtons} center={swarmCenterContent} end={missonControls} />
            </Panel>
          </div>
        </div>
      </div>
    </>
  );
}

export default React.memo(ControlPage);
