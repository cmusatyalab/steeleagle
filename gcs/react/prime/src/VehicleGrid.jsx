import Status from './Status.jsx';

function VehicleGrid({ vehicles, selectable, squadList, onToggle }) {
    return (
        <>
            {vehicles.map((v) => (
                <div className="col-12 lg:col-3 p-2" key={v.name}>
                    <Status
                        vehicle={v}
                        selectable={selectable}
                        selected={!!(squadList && squadList.includes(v.name))}
                        onToggle={() => onToggle(v.name)}
                    />
                </div>
            ))}
        </>
    );
}

export default VehicleGrid;
