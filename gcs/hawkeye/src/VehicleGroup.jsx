import { useState, useRef, useEffect } from 'react';
import './VehicleGroup.css';

import CardGroup from 'react-bootstrap/CardGroup';
import Card from 'react-bootstrap/Card';
function VehicleGroup({ selectedList }) {  


  return (
    <>      
      {/* VehicleGroup */}
       
        <CardGroup>
        {selectedList.map((name,index) => (
        <button>
            <Card key={index} bg='dark' text='light' border='light' style={{ width: '18rem'}}>
            <Card.Body>
                <Card.Title>{name}</Card.Title>
                <Card.Text>
                Some quick example text to build on the card title and make up the
                bulk of the card's content.
                </Card.Text>
            </Card.Body>
            <Card.Footer>
                Last updated 3 mins ago
            </Card.Footer>
            </Card>
        </button>
        ))}


        </CardGroup>
    </>
  );
}

export default VehicleGroup;