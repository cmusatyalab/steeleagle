import { useState, useRef, useEffect } from 'react';
import './DroneCard.css';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'

import Card from 'react-bootstrap/Card';
import Badge from 'react-bootstrap/Badge';
import Stack from 'react-bootstrap/Stack'
import Button from 'react-bootstrap/Button';


function DroneCard({ data, onClick }) {
    var battery_icon = ""
    var battery_style = "success"
    if (data.battery > 75) {
        battery_icon ="fa-battery-full"
        battery_style="success"
    }
    else if (data.battery <= 75 && data.battery >50) {
        battery_icon ="fa-battery-three-quarters"
        battery_style="success"
    }
    else if (data.battery <= 50 && data.battery >25) {
        battery_icon ="fa-battery-half"
        battery_style="warning"
    }
    else if (data.battery <= 25 && data.battery >0) {
        battery_icon ="fa-battery-quarter"
        battery_style="danger"
    }
    else {
        battery_icon ="fa-battery-empty"
        battery_style="danger"
    }


  return (
            <Button variant="dark" onClick={onClick}>
            <Card  bg='dark' text='light' border='light' >
            <Card.Body>
                <Card.Title >🚁{data.name}</Card.Title>
                <Card.Subtitle>{data.model}</Card.Subtitle>
                    <Stack direction="horizontal" gap={1} style={{ margin: '5px', }}>
                    <Badge pill bg={battery_style}>
                        <FontAwesomeIcon icon={`fas-solid ${battery_icon}`} /> {data.battery}%
                    </Badge>
                    <Badge pill bg="secondary">
                        <FontAwesomeIcon icon="fas-solid fa-satellite" /> {data.sats}
                    </Badge>
                    <Badge pill bg="primary">
                        Task: {data.task}
                    </Badge>
                    </Stack>
                    <Stack direction="horizontal" gap={1} style={{ margin: '5px', }}>

                    </Stack>
            </Card.Body>
            <Card.Footer>
                Last updated {data.last_updated} seconds ago
            </Card.Footer>
            </Card>
            </Button>

          );
}

export default DroneCard;
