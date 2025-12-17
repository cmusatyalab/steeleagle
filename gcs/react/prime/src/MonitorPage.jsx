import Status from './Status.jsx';

function MonitorPage({vehicles}) {
const list = vehicles.map((v) =>  <Status selectedVehicle={v.name} vehicles={vehicles}/>);

    return (<>{list}</>);

}

export default MonitorPage;
