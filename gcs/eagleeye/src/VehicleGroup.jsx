import { useState, useRef, useEffect } from 'react';
import './VehicleGroup.css';
import DroneCard from './DroneCard.jsx'

import CardGroup from 'react-bootstrap/CardGroup';

function VehicleGroup({ vehicles, togglefunc }) {

  return (
    <div className='vehiclegroup'>
      {/* VehicleGroup */}

        <CardGroup>
        {vehicles.map((name,index) => (
        <DroneCard key={index} data={vehicles[index]} togglefunc={togglefunc}/>
        ))}


        </CardGroup>
    </div>
  );
}

export default VehicleGroup;
