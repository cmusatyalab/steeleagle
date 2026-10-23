import Status from './Status.jsx';

function VehicleGrid({ vehicles, selectable, squadList, onToggle, cardColumnClass = 'col-12 lg:col-3 p-2' }) {
    return (
        <>
            {vehicles.map((v) => (
                <div className={cardColumnClass} key={v.name}>
                    <Status
                        vehicle={v}
                        selectable={selectable}
                        selected={!!(squadList && squadList.includes(v.name))}
                        onToggle={onToggle ? () => onToggle(v.name) : undefined}
                    />
                </div>
            ))}
        </>
    );
}

export default VehicleGrid;
