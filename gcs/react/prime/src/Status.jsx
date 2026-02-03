import React, { useState, useEffect } from "react";
import { Tag } from 'primereact/tag';
import { Card } from 'primereact/card';
import { Avatar } from 'primereact/avatar';
import { Knob } from 'primereact/knob';
import { Chip } from 'primereact/chip';
import { ProgressBar } from 'primereact/progressbar';

function Status({ vehicle }) {
    if (vehicle) {
        let last_updated = `${Math.ceil(vehicle.last_updated)} sec` || 'Unknown'
        let battery_severity = "info";
        let gps_severity = "info";
        let compass_severity = "info";

        //consult protocol/telemetry.proto for enum mappings
        switch (vehicle.battery) {
            case 0:
                battery_severity = "success";
                break;
            case 1:
                battery_severity = "warning";
                break;
            case 2:
                battery_severity = "danger";
                break;
        };

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
                <Card style={{ backgroundColor: 'var(--surface-0)' }} subTitle={`${vehicle.name} (${vehicle.model})`}>
                    <div className="flex flex-row gap-2">
                        <ProgressBar className="w-full flex align-items-center justify-content-center" value={vehicle.battery} />
                    </div>
                    <div className="flex flex-row gap-2">
                        <div className="flex flex-column flex-wrap align-content-center">
                            <Knob className="flex align-items-center justify-content-center" strokeWidth={5} size={70} value={vehicle.velocity.x_vel.toFixed(1)} min={-10} max={10} valueTemplate={'{value} m/s'} />
                            <Tag className="flex align-items-center justify-content-center" rounded value="X" icon="pi pi-gauge" />
                        </div>
                        <div className="flex flex-column flex-wrap align-content-center">
                            <Knob className="flex align-items-center justify-content-center" strokeWidth={5} size={70} value={vehicle.velocity.y_vel.toFixed(1)} min={-10} max={10} valueTemplate={'{value} m/s'} />
                            <Tag className="flex align-items-center justify-content-center" rounded value="Y" icon="pi pi-gauge" />
                        </div>
                        <div className="flex flex-column flex-wrap align-content-center">
                            <Knob className="flex align-items-center justify-content-center" strokeWidth={5} size={70} value={vehicle.velocity.z_vel.toFixed(1)} min={-10} max={10} valueTemplate={'{value} m/s'} />
                            <Tag className="flex align-items-center justify-content-center" rounded value="Z" icon="pi pi-gauge" />
                        </div>
                        <div className="flex flex-column flex-wrap align-items-center justify-content-end">
                            <Avatar className="m-2" size="large" shape="circle" icon="pi pi-arrow-up" style={{
                                transform: `rotate(${vehicle.bearing}deg)`,
                                transition: 'transform 0.0s ease' // Optional: adds a smooth transition
                            }} />
                            <Tag className="flex align-items-center justify-content-center" rounded value="Compass" icon="pi pi-compass" />
                        </div>

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
