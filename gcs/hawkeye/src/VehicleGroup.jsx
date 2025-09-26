import { useState, useRef, useEffect } from 'react';
import './VehicleGroup.css';
import DroneCard from './DroneCard.jsx'

import CardGroup from 'react-bootstrap/CardGroup';

function VehicleGroup({ selectedList }) {  


  return (
    <>      
      {/* VehicleGroup */}
       
        <CardGroup>
        {selectedList.map((name,index) => (
        <DroneCard name={name} index={index} data={null}/>
        ))}


        </CardGroup>
    </>
  );
}

export default VehicleGroup;