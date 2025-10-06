import { useState, useRef, useEffect } from 'react';
import { useContext } from 'react';
import './DroneCard.css';

import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'

import Card from 'react-bootstrap/Card';
import Badge from 'react-bootstrap/Badge';
import Stack from 'react-bootstrap/Stack'
import Button from 'react-bootstrap/Button';


function DroneCard({ data, togglefunc}) {
    var battery_icon = ""
    var battery_style = "success"
    var battery_text_style = "light"
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
        battery_style ="warning"
        battery_text_style = "dark"
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
            <div className={`drone-card-wrapper ${data.selected ? 'selected' : ''} me-3`}>
            <Button variant={data.selected ? "light" : "dark"} onClick={() => togglefunc(data.name)} style={{ padding: 0, border: 'none' }}>
            <div className="drone-card-inner">
            <Card  bg='dark' text='light' border=''>
            <Card.Body>
                <Card.Title>{data.name} <sub>[{data.type}]</sub></Card.Title>
                <Card.Subtitle>{data.model}</Card.Subtitle>
                    <Stack direction="horizontal" gap={1} style={{ margin: '5px', justifyContent: 'center',}}>
                    <Badge pill bg={battery_style} text={battery_text_style}>
                        <FontAwesomeIcon icon={`fas-solid ${battery_icon}`} /> {data.battery}%
                    </Badge>
                    <Badge pill bg="secondary">
                        <FontAwesomeIcon icon="fas-solid fa-satellite" /> {data.sats}
                    </Badge>
                    <Badge pill bg="secondary">
                        {data.task}
                    </Badge>
                    </Stack>
                    <Stack direction="horizontal" gap={1} style={{ margin: '5px', }}>
                    </Stack>
            </Card.Body>
            <Card.Footer>
                Last updated {data.last_updated} seconds ago
            </Card.Footer>
            </Card>
            </div>
            </Button>
            </div>

          );
}

export default DroneCard;
