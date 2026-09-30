import { useMemo, useState } from 'react';
import { Button } from 'primereact/button';
import { Toolbar } from 'primereact/toolbar';
import { ButtonGroup } from 'primereact/buttongroup';
import { Tooltip } from 'primereact/tooltip';
import { FileUpload } from 'primereact/fileupload';
import { Image } from 'primereact/image';
import { Dropdown } from 'primereact/dropdown';
import React from 'react';
import { getApiUrl } from './urls.js';
import Mapbox from './Mapbox.jsx';
import { toggleVehicleInSquad } from './squadUtils.js';
import { STYLE_OPTIONS } from './mapStyles.js';
import MissionUploadProgress from './MissionUploadProgress.jsx';
import { streamUpload, initialUploadState, applyUploadEvent, isUploadFinished, finishUpload } from './missionUpload.js';

const cancelOptions = { icon: 'pi pi-fw pi-times', iconOnly: true, className: 'custom-cancel-btn p-button-danger' };
const chooseOptions = { label: 'Select...', icon: 'pi pi-fw pi-file', iconOnly: false, className: 'custom-choose-btn p-button-primary' };
const uploadOptions = { icon: 'pi pi-fw pi-cloud-upload', iconOnly: true, className: 'custom-upload-btn p-button-info' };

// Shared between the map and the video panel next to it so they're always
// the same height (passed to Mapbox as mapHeight, overriding its own
// '20rem' default) -- bumped up from that default now that removing the
// Swarm Controls Panel wrapper below frees up the vertical room for it.
const videoPanelHeight = '26rem';

function ControlPage({ vehicles, selectedVehicle, setSelectedVehicle, tracking, setTracking,
  showDetections, onToggleDetections, toast, onCommand,
  setManualControl, squadList, setSquadList, takeOffAltitude, controlGroups,
  uploadState, setUploadState }) {
  const mapPanelSize = 0;
  const [mapStyle, setMapStyle] = useState('streets');
  const uploadInProgress = uploadState != null && !isUploadFinished(uploadState);

  const uploadHandler = async (event) => {
    if (uploadInProgress) {
      toast.current.show({ severity: 'warn', summary: 'Upload already in progress', detail: `Wait for the current mission upload to finish before starting another.` });
      return;
    }
    if (squadList == null || squadList.length == 0) {
      toast.current.show({ severity: 'warn', summary: 'No Vehicles in Squad', detail: `Please select at least one vehicle to control.` });
      return;
    }
    const targets = [...squadList];
    const form = new FormData();
    for (const file of event.files) form.append('files', file);
    for (const vehicle of targets) form.append('vehicles', vehicle);
    setUploadState(initialUploadState(targets));
    try {
      await streamUpload(getApiUrl('/api/upload'), { method: 'POST', body: form },
        (ev) => setUploadState(s => applyUploadEvent(s, ev)));
      setUploadState(s => finishUpload(s));
      event.options.clear();
    } catch (e) {
      setUploadState(s => applyUploadEvent(s, { type: 'error', detail: e.message }));
    }
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
      <FileUpload className="m-2" itemTemplate={itemTemplate} chooseOptions={chooseOptions} uploadOptions={uploadOptions} cancelOptions={cancelOptions} mode="advanced" name="files" multiple maxFileSize={128 * 1024 * 1024} customUpload uploadHandler={uploadHandler} disabled={uploadInProgress} />
      <Button icon="pi pi-play-circle" label="Start Mission" className="m-2 p-button-success" onClick={onMissionStart} />
    </>
  ), [uploadHandler, onMissionStart, uploadInProgress]);

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

  const onToggleVehicle = (name) => setSquadList((prev) => toggleVehicleInSquad(prev, name));

  return (
    <div className="p-2">
      <div className="flex flex-column">
        <div className="flex align-items-center gap-2 mb-2 px-2 py-1 border-round" style={{ backgroundColor: 'var(--surface-card)', border: '1px solid var(--surface-border)' }}>
          {/* Left/center/right flex-1 sections roughly align with the map
              and video panels below. */}
          <div className="flex-1 flex justify-content-start">
            <Dropdown value={mapStyle} options={STYLE_OPTIONS} onChange={(e) => setMapStyle(e.value)}
              className="w-full md:w-9rem" />
          </div>
          <div className="flex align-items-center gap-1">
            <Button
              size="small"
              outlined={!tracking}
              severity={tracking ? undefined : 'secondary'}
              icon={tracking ? 'pi pi-bullseye' : 'pi pi-map'}
              label="Vehicle Tracking"
              tooltip={`Tracking ${tracking ? 'On' : 'Off'}: recenters the map on the selected vehicle`}
              tooltipOptions={{ position: 'bottom' }}
              onClick={() => setTracking(!tracking)}
              aria-label="Toggle tracking"
            />
            <Button
              size="small"
              outlined={!showDetections}
              severity={showDetections ? undefined : 'secondary'}
              icon={showDetections ? 'pi pi-eye' : 'pi pi-eye-slash'}
              label="Show Detections"
              tooltip={`Detections ${showDetections ? 'Shown' : 'Hidden'}: toggles bounding boxes on the video stream`}
              tooltipOptions={{ position: 'bottom' }}
              onClick={() => onToggleDetections(!showDetections)}
              aria-label="Toggle show detections"
            />
          </div>
          <div className="flex-1 flex justify-content-end">
            <Dropdown value={selectedVehicle} checkmark={true} onChange={(e) => setSelectedVehicle(e.value)} options={vehicleNames} useOptionAsValue optionLabel="name"
              placeholder="Select Video Feed" className="w-full md:w-14rem" />
          </div>
        </div>
        <div className="grid m-0">
          <div className="col-12 lg:col-6 p-2">
            <Mapbox selectedVehicle={selectedVehicle} vehicles={vehicles} mapPanelSize={mapPanelSize} tracking={tracking}
              mapHeight={videoPanelHeight} squadList={squadList} onToggleVehicle={onToggleVehicle} controlGroups={controlGroups} mapStyle={mapStyle} />
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
        <MissionUploadProgress state={uploadState} onDismiss={() => setUploadState(null)} />
      </div>
    </div>
  );
}

export default React.memo(ControlPage);
