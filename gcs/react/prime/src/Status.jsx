import React from "react";
import { Card } from 'primereact/card';
import { Badge } from 'primereact/badge';
import { ProgressBar } from 'primereact/progressbar';
import { vehicleSpeed, isVehicleDisconnected, vehicleStatus, vehicleStatusColor } from './mapUtils.js';

const cardPassthrough = {
    body: { style: { padding: '0.4rem 0.75rem' } },
    content: { style: { padding: 0 } },
};

function Status({ vehicle, selectable, selected, onToggle }) {
    if (!vehicle) {
        return (<>No vehicles connected.</>);
    }

    const disconnected = isVehicleDisconnected(vehicle);
    const showCheck = !!(selectable && selected);
    const status = vehicleStatus(disconnected, showCheck);
    const statusColor = vehicleStatusColor(status);

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

    return (
        <Card
            pt={cardPassthrough}
            style={{
                position: 'relative',
                backgroundColor: showCheck ? `color-mix(in srgb, ${statusColor} 12%, var(--surface-0))` : 'var(--surface-0)',
                width: '100%',
                cursor: selectable ? 'pointer' : 'default',
                border: showCheck ? `2px solid ${statusColor}` : '2px solid transparent',
                opacity: disconnected ? 0.6 : 1,
            }}
            onClick={selectable ? onToggle : undefined}
        >
            {showCheck && (
                <Badge
                    value={<i className="pi pi-check" style={{ fontSize: '0.6rem' }} />}
                    style={{ position: 'absolute', top: '-6px', right: '-6px', backgroundColor: statusColor, color: '#ffffff' }}
                />
            )}
            <div className="flex flex-column gap-1">
                <div className="flex align-items-center gap-2">
                    <i
                        className={disconnected ? "pi pi-times" : "pi pi-link"}
                        style={{ color: statusColor, fontSize: '0.8rem' }}
                        title={disconnected ? "Disconnected" : "Online"}
                    />
                    <span className="font-semibold text-sm">{vehicle.name}</span>
                    <span className="text-color-secondary text-xs">{vehicle.model}</span>
                </div>
                <div className="flex align-items-center gap-2">
                    <ProgressBar color={`var(--${battery_severity})`} style={{ width: '3rem', height: '4px' }} value={vehicle.battery} showValue={false} />
                    <span className="text-xs font-semibold" style={{ minWidth: '2rem', textAlign: 'right' }}>{Math.round(vehicle.battery)}%</span>
                    <span className="flex-1" />
                    <span className="text-xs text-color-secondary flex align-items-center gap-1">
                        <i className="pi pi-arrow-up" style={{ display: 'inline-block', transform: `rotate(${vehicle.bearing}deg)`, fontSize: '0.65rem' }} />
                        {Math.round(vehicle.bearing)}°
                    </span>
                    <span className="text-xs text-color-secondary">{speed.toFixed(1)} m/s</span>
                    <span className="text-xs text-color-secondary flex align-items-center gap-1">
                        <i className="pi pi-wifi" style={{ fontSize: '0.65rem' }} />
                        {vehicle.sats}
                    </span>
                </div>
            </div>
        </Card>
    );
}

export default Status;
