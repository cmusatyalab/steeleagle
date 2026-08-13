import { useState, useMemo, useCallback } from 'react';
import { Button } from 'primereact/button';
import { Chip } from 'primereact/chip';
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
import { toggleVehicleInSquad, recallControlGroup, squadMatchesGroup } from './squadUtils.js';
import { sortVehiclesForDisplay, vehicleStatus, vehicleStatusColor, vehicleStatusRailFill, isVehicleDisconnected } from './mapUtils.js';

const cancelOptions = { icon: 'pi pi-fw pi-times', iconOnly: true, className: 'custom-cancel-btn p-button-danger' };
const chooseOptions = { label: 'Select...', icon: 'pi pi-fw pi-file', iconOnly: false, className: 'custom-choose-btn p-button-primary' };
const uploadOptions = { icon: 'pi pi-fw pi-cloud-upload', iconOnly: true, className: 'custom-upload-btn p-button-info' };
const controlGroupDigits = ['1', '2', '3'];

// Shared between the map and the video panel next to it so they're always
// the same height (passed to Mapbox as mapHeight, overriding its own
// '20rem' default) -- bumped up from that default now that removing the
// Swarm Controls Panel wrapper below frees up the vertical room for it.
const videoPanelHeight = '26rem';

function ControlPage({ vehicles, selectedVehicle, tracking, toast, onCommand,
  setManualControl, squadList, setSquadList, takeOffAltitude, controlGroups }) {
  const [mapPanelSize] = useState(0);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const sortedVehicles = useMemo(() => sortVehiclesForDisplay(vehicles, squadList), [vehicles, squadList]);
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
  const connectedVehicleNames = useMemo(
    () => vehicles.filter(v => !isVehicleDisconnected(v)).map(v => v.name),
    [vehicles]
  );

  const onSelectAllSquad = useCallback(() => setSquadList([...connectedVehicleNames]), [connectedVehicleNames, setSquadList]);
  const onClearSquad = useCallback(() => setSquadList([]), [setSquadList]);
  const onRecallGroup = useCallback((digit) => setSquadList(recallControlGroup(controlGroups, digit)), [controlGroups, setSquadList]);

  const onToggleVehicle = (name) => setSquadList((prev) => toggleVehicleInSquad(prev, name));

  const squadHeaderTemplate = (options) => (
    <div className={`${options.className} flex-column align-items-stretch`}>
      <div className="flex align-items-center justify-content-between mb-2">
        <div className="flex align-items-center gap-1">
          <Button size="small" rounded text label="" icon="pi pi-chevron-left" tooltip="Collapse" tooltipOptions={{ position: 'bottom' }} onClick={() => setSidebarCollapsed(true)} aria-label="Collapse squad list" />
          <span className="font-bold">Squad</span>
        </div>
        <Chip label={`${(squadList ?? []).length}/${vehicleNames.length} selected`} icon="pi pi-users" />
      </div>
      <div className="flex align-items-center justify-content-between flex-wrap gap-2">
        <div className="flex align-items-center gap-1">
          <Button size="small" rounded text label="" icon="pi pi-check-square" tooltip="Select All" tooltipOptions={{ position: 'bottom' }} onClick={onSelectAllSquad} aria-label="Select All" />
          <Button size="small" rounded text label="" icon="pi pi-times" tooltip="Clear" tooltipOptions={{ position: 'bottom' }} onClick={onClearSquad} aria-label="Clear" />
        </div>
        <ButtonGroup>
          {controlGroupDigits.map((digit) => {
            const hasVehicles = controlGroups[digit]?.length > 0;
            const isActive = hasVehicles && squadMatchesGroup(squadList, controlGroups, digit);
            return (
            <Button
              key={digit}
              size="small"
              outlined={!hasVehicles}
              severity={!hasVehicles ? 'secondary' : isActive ? 'success' : undefined}
              label={digit}
              tooltip={`Group ${digit}: ${(controlGroups[digit] ?? []).length} vehicles${isActive ? ' (currently selected)' : ''}`}
              tooltipOptions={{ position: 'bottom' }}
              onClick={() => onRecallGroup(digit)}
            />
            );
          })}
        </ButtonGroup>
      </div>
    </div>
  );

  return (
    <>
      <div className="flex flex-column lg:flex-row m-0">
        <div
          className={sidebarCollapsed ? "p-2" : "p-2 w-full lg:w-3"}
          style={sidebarCollapsed ? { width: '56px', flexShrink: 0 } : undefined}
        >
          {sidebarCollapsed ? (
            <div className="flex flex-column align-items-center gap-3 pt-2">
              <Button size="small" rounded text label="" icon="pi pi-chevron-right" tooltip="Expand" tooltipOptions={{ position: 'right' }} onClick={() => setSidebarCollapsed(false)} aria-label="Expand squad list" />
              {sortedVehicles.map((v) => {
                const disconnected = isVehicleDisconnected(v);
                const status = vehicleStatus(disconnected, !!(squadList && squadList.includes(v.name)));
                return (
                  <span
                    key={v.name}
                    title={`${v.name} (${status})`}
                    onClick={disconnected ? undefined : () => onToggleVehicle(v.name)}
                    style={{
                      width: '12px', height: '12px', borderRadius: '50%',
                      cursor: disconnected ? 'not-allowed' : 'pointer',
                      backgroundColor: vehicleStatusRailFill(status),
                      border: `2px solid ${vehicleStatusColor(status)}`,
                      opacity: disconnected ? 0.6 : 1,
                    }}
                  />
                );
              })}
            </div>
          ) : (
            <Panel headerTemplate={squadHeaderTemplate} className="h-full">
              <div className="grid m-0" style={{ maxHeight: 'calc(100vh - 280px)', overflowY: 'auto' }}>
                <VehicleGrid vehicles={sortedVehicles} selectable squadList={squadList} onToggle={onToggleVehicle} cardColumnClass="col-12 p-2" />
              </div>
            </Panel>
          )}
        </div>
        <div className="p-2 flex-1" style={{ minWidth: 0 }}>
          <div className="flex flex-column">
            <div className="grid m-0">
              <div className="col-12 lg:col-6 p-2">
                <Mapbox selectedVehicle={selectedVehicle} vehicles={vehicles} mapPanelSize={mapPanelSize} tracking={tracking}
                  mapHeight={videoPanelHeight} squadList={squadList} onToggleVehicle={onToggleVehicle} controlGroups={controlGroups} />
              </div>
              <div className="col-12 lg:col-6 p-2">
                <div style={{ height: videoPanelHeight, backgroundColor: '#000' }}>
                  <Image imageStyle={{ width: '100%', height: '100%', objectFit: 'contain' }} pt={{ image: { id: 'image_stream' } }} src="nostream.png" />
                </div>
              </div>
            </div>
            <div className="my-2" style={{ overflowX: 'auto' }}>
              <Toolbar className="w-full flex-nowrap" start={controlButtons} end={missonControls} />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

export default React.memo(ControlPage);
