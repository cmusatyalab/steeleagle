
import { useRef, useEffect, useState } from 'react';
import { Badge } from 'primereact/badge';
import { Button } from 'primereact/button';
import { ToggleButton } from 'primereact/togglebutton';
import { FloatLabel } from 'primereact/floatlabel';
import { Toast } from 'primereact/toast';
import { Sidebar } from 'primereact/sidebar';
import { Splitter, SplitterPanel } from 'primereact/splitter';
import { Toolbar } from 'primereact/toolbar';
import { Dropdown } from 'primereact/dropdown';
import { Tooltip } from 'primereact/tooltip';
import { FileUpload } from 'primereact/fileupload';
import { DataTable } from 'primereact/datatable';
import { Column } from 'primereact/column';
import { Image } from 'primereact/image';
import { WEBSERVER_URL, FASTAPI_URL } from './config.js';
import Status from './Status.jsx';
import Mapbox from './Mapbox.jsx';

function ControlPage({vehicles, selectedVehicle, tracking, toast, onCommand}) {
  const [mapPanelSize, setMapPanelSize] = useState(0);
  const [armed, setArmed] = useState(false);

   const onProgress = () => {
     toast.current.show({ severity: 'info', summary: 'In Progress', detail: 'Uploading files...' });
   };

   function sleep(ms) {
     return new Promise(resolve => setTimeout(resolve, ms));
   }
   const uploadHandler = async (event) => {
     const body = {};
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
     const response = await fetch(`${FASTAPI_URL}/api/upload`, requestOptions);
     if (!response.ok) {
       const result = await response.json();
       toast.current.show({ severity: 'error', summary: 'Upload Mission Error', detail: `HTTP error! status: ${result.detail}` });
     }
     else {
       const result = await response.json();
       toast.current.show({ severity: 'success', summary: 'Upload Mission', detail: `${result}` });
     }

   };


   const onUploadComplete = () => {
     toast.current.show({ severity: 'success', summary: 'File Uploaded', detail: 'The mission has been uploaded.' });
   };

   const onMissionStart = async () => {
     const requestOptions = {
       method: 'POST',
       headers: { 'Content-Type': 'application/json' },
     };
     const response = await fetch(`${FASTAPI_URL}/api/start`, requestOptions);
     if (!response.ok) {
       const result = await response.json();
       toast.current.show({ severity: 'error', summary: 'Mission Error', detail: `HTTP error! status: ${result.detail}` });
     }
     else {
       const result = await response.json();
       toast.current.show({ severity: 'success', summary: 'Mission Success', detail: `${result}` });
     }
   }

  const cancelOptions = { icon: 'pi pi-fw pi-times', iconOnly: true, className: 'custom-cancel-btn p-button-danger' };
  const chooseOptions = { label: 'Select...', icon: 'pi pi-fw pi-file', iconOnly: false, className: 'custom-choose-btn p-button-primary' };
  const uploadOptions = { icon: 'pi pi-fw pi-cloud-upload', iconOnly: true, className: 'custom-upload-btn p-button-info' };
  const itemTemplate = (file, props) => {
    return (
      <span className="text-left ml-3">
        {file.name}
      </span>

    );
  };
  const endContent = (
    <>
      <Tooltip target=".custom-choose-btn" content="Select Mission Files" position="bottom" />
      <Tooltip target=".custom-upload-btn" content="Upload Mission" position="bottom" />
      <Tooltip target=".custom-cancel-btn" content="Clear Selected Files" position="bottom" />
      <FileUpload className="m-2" itemTemplate={itemTemplate} chooseOptions={chooseOptions} uploadOptions={uploadOptions} cancelOptions={cancelOptions} mode="advanced" name="mission[]" url={'/api/upload'} multiple accept="application/vnd.google-earth.kml+xml,application/json" maxFileSize={10000} customUpload uploadHandler={uploadHandler} onProgress={onProgress} onUpload={onUploadComplete} />
      <Button icon="pi pi-play-circle" label="Start Mission" className="m-2 p-button-success" onClick={() => onMissionStart()} />
    </>
  );

  const centerContent = (
    <>
      <Status selectedVehicle={selectedVehicle} vehicles={vehicles} />
    </>
  );

  const startContent = (
    <>
      <ToggleButton onLabel="Armed" offLabel="Disarmed" onIcon="pi pi-times pi-spin" offIcon="pi pi-ban"
        checked={armed} onChange={(e) => setArmed(e.value)} className="w-9rem mr-2" />
      <Button icon="pi pi-home" label="RTH" className="mr-2" onClick={() => onCommand({ rth: true })} />
      <Button icon="pi pi-stop-circle" label="Hover" onClick={() => onCommand({ hold: true })} />
    </>
  );

  return (
    <>
      <Splitter style={{ height: '720px' }} layout="vertical" onResizeEnd={(event) => setMapPanelSize(event.sizes[0])}>
        <SplitterPanel className="flex align-items-center justify-content-center" size={80} minSize={60}>
          <Splitter style={{ height: '100%' }} className="flex align-items-center justify-content-center" onResizeEnd={(event) => setMapPanelSize(event.sizes[0])}>
            <SplitterPanel style={{ height: '100%' }} className="flex align-items-center justify-content-center m-2" size={50} minSize={30}>
              <Mapbox selectedVehicle={selectedVehicle} vehicles={vehicles} mapPanelSize={mapPanelSize} tracking={tracking} />
            </SplitterPanel>
            <SplitterPanel style={{ height: '100%' }} className="flex align-items-center justify-content-center m-2" size={50} minSize={30}>
              <Image height="90%" width="90%" src={`${WEBSERVER_URL}/raw/${selectedVehicle}/latest.jpg?time=${Math.floor(Date.now() / 1000)}`} preview downloadable="true"></Image>
            </SplitterPanel>
          </Splitter>
        </SplitterPanel>
        <SplitterPanel className="flex align-items-center justify-content-center m-2" size={20} minSize={20}>
          <Toolbar style={{ width: '100%' }} start={startContent} center={centerContent} end={endContent} />
        </SplitterPanel>
      </Splitter>
    </>
  );
}

export default ControlPage;
