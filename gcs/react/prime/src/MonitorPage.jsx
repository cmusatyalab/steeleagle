import Status from './Status.jsx';

function MonitorPage({vehicles}) {
const list = vehicles.map((v) =>  <Status vehicle={v}/>);

    return (<>{list}</>);

}

export default MonitorPage;
