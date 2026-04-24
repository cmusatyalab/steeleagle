import React, { useState, useEffect } from "react";
import { Tag } from 'primereact/tag';
import { Card } from 'primereact/card';
import { Avatar } from 'primereact/avatar';
import { Knob } from 'primereact/knob';
import { Badge } from 'primereact/badge';
import { ProgressBar } from 'primereact/progressbar';

function Status({ vehicle }) {
    if (vehicle) {
        let last_updated = `${Math.ceil(vehicle.last_updated)} sec` || 'Unknown'
        let disconnected = false;
        if (vehicle.last_updated > 5) {
            disconnected = true;
        }

        let battery_severity = "info";
        let gps_severity = "info";
        let compass_severity = "info";

        //consult protocol/telemetry.proto for enum mappings
        if (vehicle.battery <= 25) {
            battery_severity = "red-500";
        } else if (vehicle.battery <= 50) {
            battery_severity = "orange-500";
        } else {
            battery_severity = "green-500";
        }

        switch (vehicle.mag) {
            case 0:
                compass_severity = "success";
                break;
            case 1:
                compass_severity = "danger";
                break;
        };

        switch (vehicle.sats) {
            case 0:
                gps_severity = "success";
                break;
            case 1:
                gps_severity = "warning";
                break;
            case 2:
                gps_severity = "danger";
                break;
        };

        return (
            <>
                <Card style={{ backgroundColor: 'var(--surface-0)', width: '100%' }} subTitle={`${vehicle.name} (${vehicle.model})`}>
                    <div className="flex flex-row gap-2 m-2">
                        <ProgressBar color={`var(--${battery_severity})`} className="w-full flex align-items-center justify-content-center" value={vehicle.battery} />
                        {disconnected && <Tag icon="pi pi-times" severity="danger" value="Disconnected"></Tag>}
                        {!disconnected && <Tag icon="pi pi-link" severity="info" value="Online"></Tag>}
                    </div>
                    <div className="flex flex-row flex-wrap justify-content-center gap-2 m-2">
                        <div className="flex flex-column align-items-center">
                            <Knob strokeWidth={5} size={60} value={vehicle.velocity.x_vel.toFixed(1)} min={-10} max={10} valueTemplate={'{value} m/s'} />
                            <Tag rounded value="X" icon="pi pi-gauge" />
                        </div>
                        <div className="flex flex-column align-items-center">
                            <Knob strokeWidth={5} size={60} value={vehicle.velocity.y_vel.toFixed(1)} min={-10} max={10} valueTemplate={'{value} m/s'} />
                            <Tag rounded value="Y" icon="pi pi-gauge" />
                        </div>
                        <div className="flex flex-column align-items-center">
                            <Knob strokeWidth={5} size={60} value={vehicle.velocity.z_vel.toFixed(1)} min={-10} max={10} valueTemplate={'{value} m/s'} />
                            <Tag rounded value="Z" icon="pi pi-gauge" />
                        </div>
                        <div className="flex flex-column align-items-center justify-content-end">
                            <Avatar className="m-2" size="large" shape="circle" icon="pi pi-arrow-up" style={{
                                transform: `rotate(${vehicle.bearing}deg)`,
                                transition: 'transform 0.0s ease'
                            }} />
                            <Tag rounded value="Compass" icon="pi pi-compass" />
                        </div>
                    </div>
                    <div className="flex flex-row flex-wrap justify-content-center gap-2 m-2">
                        <Tag value={`Sats: ${vehicle.sats}`} rounded />
                    </div>
                </Card >
            </>
        );
    }
    else {
        return (<>No vehicles connected.</>);
    }
}

export default Status;
