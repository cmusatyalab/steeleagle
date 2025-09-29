import { useState, useRef, useEffect } from 'react';
import './VehicleGroup.css';
import DroneCard from './DroneCard.jsx'

import CardGroup from 'react-bootstrap/CardGroup';

function VehicleGroup({ selectedList, vehicles, onClick }) {


  return (
    <div className='vehiclegroup'>
      {/* VehicleGroup */}

        <CardGroup>
        {vehicles.map((name,index) => (
        <DroneCard key={index} data={vehicles[index]} onClick={onClick}/>
        ))}


        </CardGroup>
    </div>
  );
}

export default VehicleGroup;
