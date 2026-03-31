import Status from './Status.jsx';
import Mapbox from './Mapbox.jsx';
import { Panel } from 'primereact/panel';

function MonitorPage({ vehicles, detectedObjects }) {


    return (
        <>
            <div className="flex flex-column">
                <Panel header="Monitor" className="h-full" >
                    <div className="grid m-0">
                        <div className="col-12 lg:col-6 p-2"></div>
                        <Mapbox selectedVehicle={null} tracking={false} mapPanelSize={0} vehicles={vehicles} detectedObjects={detectedObjects} mapHeight="30rem" />
                        {vehicles.map((v) => <div className="col-12 lg:col-3 p-2"> <Status vehicle={v} /> </div>)}
                    </div>
                </Panel >

            </div >
        </>
    );
}

export default MonitorPage;
