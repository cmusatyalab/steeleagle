import React, { useState, useEffect } from "react";
import { Tag } from 'primereact/tag';
import { Card } from 'primereact/card';


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
                <Card style={{ backgroundColor: 'var(--surface-0)'}} title={vehicle.name} subTitle={vehicle.model}>
                    <Tag className="mr-2" icon="pi pi-power-off" severity={battery_severity} value="Battery"></Tag>
                    <Tag className="mr-2" icon="pi pi-compass" severity={compass_severity} value="Compass"></Tag>
                    <Tag className="mr-2" icon="pi pi-map-marker" severity={gps_severity} value="GPS"></Tag>
                    <Tag className="mr-2" icon="pi pi-stopwatch" severity="info" value={last_updated}></Tag>
                </Card>
            </>
        );
    }
    else {
        return (<>No vehicles connected.</>);
    }
}

export default Status;
