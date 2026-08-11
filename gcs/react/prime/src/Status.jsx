import React from "react";
import { Tag } from 'primereact/tag';
import { Card } from 'primereact/card';
import { Badge } from 'primereact/badge';
import { ProgressBar } from 'primereact/progressbar';
import { vehicleColor, vehicleSpeed } from './mapUtils.js';

function Status({ vehicle, selectable, selected, onToggle }) {
    if (!vehicle) {
        return (<>No vehicles connected.</>);
    }

    const color = vehicleColor(vehicle.name);
    const disconnected = vehicle.last_updated > 5;

    let battery_severity = "info";

    //consult protocol/telemetry.proto for enum mappings
    if (vehicle.battery <= 25) {
        battery_severity = "red-500";
    } else if (vehicle.battery <= 50) {
        battery_severity = "orange-500";
    } else {
        battery_severity = "green-500";
    }

    const speed = vehicleSpeed(vehicle.velocity);
    const showCheck = !!(selectable && selected);

    return (
        <Card
            style={{
                position: 'relative',
                backgroundColor: showCheck ? `color-mix(in srgb, ${color} 12%, var(--surface-0))` : 'var(--surface-0)',
                width: '100%',
                cursor: selectable ? 'pointer' : 'default',
                border: showCheck ? `2px solid ${color}` : '2px solid transparent'
            }}
            onClick={selectable ? onToggle : undefined}
        >
            {showCheck && (
                <Badge
                    value={<i className="pi pi-check" style={{ fontSize: '0.6rem' }} />}
                    style={{ position: 'absolute', top: '-6px', right: '-6px', backgroundColor: color, color: '#ffffff' }}
                />
            )}
            <div className="flex align-items-center gap-2">
                <span style={{ display: 'inline-block', width: '10px', height: '10px', minWidth: '10px', borderRadius: '50%', backgroundColor: color }} />
                <span className="font-semibold">{vehicle.name}</span>
                <span className="text-color-secondary text-sm">{vehicle.model}</span>
            </div>
            <div className="flex align-items-center gap-2 mt-2">
                <ProgressBar color={`var(--${battery_severity})`} className="w-full" style={{ height: '6px' }} value={vehicle.battery} showValue={false} />
                <span className="text-sm font-semibold" style={{ minWidth: '2.5rem', textAlign: 'right' }}>{Math.round(vehicle.battery)}%</span>
                <Tag icon={disconnected ? "pi pi-times" : "pi pi-link"} severity={disconnected ? "danger" : "info"} value={disconnected ? "Disconnected" : "Online"} />
            </div>
            <div className="flex align-items-center gap-3 mt-2 text-sm text-color-secondary">
                <span className="flex align-items-center gap-1">
                    <i className="pi pi-arrow-up" style={{ display: 'inline-block', transform: `rotate(${vehicle.bearing}deg)` }} />
                    {Math.round(vehicle.bearing)}°
                </span>
                <span>{speed.toFixed(1)} m/s</span>
                <span className="flex align-items-center gap-1">
                    <i className="pi pi-wifi" />
                    {vehicle.sats}
                </span>
            </div>
        </Card>
    );
}

export default Status;
