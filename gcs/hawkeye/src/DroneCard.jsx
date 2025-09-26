import { useState, useRef, useEffect } from 'react';
import './DroneCard.css';

import Card from 'react-bootstrap/Card';
import Badge from 'react-bootstrap/Badge';
import Stack from 'react-bootstrap/Stack'
import Button from 'react-bootstrap/Button';
function DroneCard({ name, index, data }) {  


  return (
            <Button variant="dark">
            <Card key={index} bg='dark' text='light' border='light' >
            <Card.Body>
                <Card.Title >🚁{name}</Card.Title>
                <Card.Subtitle>Parrot ANAFI</Card.Subtitle>
                
                    <Stack direction="horizontal" gap={1} style={{ margin: '5px', }}>
                    <Badge pill bg="success">
                        Battery: 97%
                    </Badge>
                    <Badge pill bg="warning">
                        Satellites: 12
                    </Badge>
                    </Stack>
                    <Stack direction="horizontal" gap={1} style={{ margin: '5px', }}>
                    <Badge pill bg="danger">
                        Task: idle
                    </Badge>
                    <Badge pill bg="info">
                        Something else
                    </Badge>
                  
                    </Stack>
            </Card.Body>
            <Card.Footer>
                Last updated 3 mins ago
            </Card.Footer>
            </Card>
            </Button>

          );
}

export default DroneCard;