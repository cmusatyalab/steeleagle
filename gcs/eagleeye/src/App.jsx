import { useState } from 'react'
import { useReducer } from 'react'
import { useRef, useEffect } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { fas } from '@fortawesome/free-solid-svg-icons'
import { library } from '@fortawesome/fontawesome-svg-core'

import ListGroup from 'react-bootstrap/ListGroup';
import Badge from 'react-bootstrap/Badge'

import Mapbox from './Mapbox.jsx'
import Drawer from './Drawer.jsx'
import VehicleGroup from './VehicleGroup.jsx'
import GameControls from './GameControls.jsx'
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css'
import ListGroupItem from 'react-bootstrap/esm/ListGroupItem.js'

library.add(fas)

var adjective = ["Steel", "Iron", "Brass","Golden", "Liquid", "Solid", "Adamantium", "Titantium"]
var object = ["Eagle", "Hawk", "Sparrow", "Condor", "Parrot", "Lark", "Falcon"]
var models = ["Parrot ANAFI", "Generic MAVLink", "Ascent Systems Spirit", "DJI Mini 4 Pro"]
var types = ["UAV", "UGV", "USV"]

function getRandomInt(min, max) {
  const minCeiled = Math.ceil(min);
  const maxFloored = Math.floor(max);
  return Math.floor(Math.random() * (maxFloored - minCeiled) + minCeiled); // The maximum is exclusive and the minimum is inclusive
}

function getRandomName() {
  return adjective[Math.floor(Math.random() * adjective.length)] + " " + object[Math.floor(Math.random() * object.length)];
}

function getRandomType() {
  return types[Math.floor(Math.random() * types.length)];
}

function generateVehicleData() {
  var vehicles = [];
  var number = getRandomInt(1,10);
  for (var i=0; i< number; i++) {
    vehicles[i] = ({ name: getRandomName(), type: getRandomType(), model: models[Math.floor(Math.random() * models.length)], battery: getRandomInt(0,100), sats: getRandomInt(0,25), task: Math.random() >0.5 ? "idle" : "tracking" , last_updated: getRandomInt(0,30), selected: false})
  }
  return vehicles;
}


function App() {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerWidth, setDrawerWidth] = useState(0);
  const [vehicles, setVehicles] = useState(generateVehicleData());
  const handleDrawerToggle = () => {
    setIsDrawerOpen(!isDrawerOpen);
  };

  const handleDrawerWidthChange = (width) => {
    setDrawerWidth(width);
  };

    const toggleSelected = (name) => {
    setVehicles(vehicles.map(vehicle =>
      vehicle.name === name ? { ...vehicle, selected: !vehicle.selected } : vehicle
    ));
  };



  return (
    <>
      <nav className="App-header">
        <div className="nav-left">
          <button className="nav-hamburger" onClick={handleDrawerToggle}>
            <FontAwesomeIcon icon={`fas-solid ${isDrawerOpen ? "fa-eye-slash" : "fa-eye"}`} />
          </button>
          <span className="nav-title">Hawkeye</span>
          {vehicles.filter(item => item.selected).map(item => (
            <Badge pill bg="light" text="dark" key={item.name}>{item.name}</Badge>
          ))}
        </div>
      </nav>

      <Drawer
        isOpen={isDrawerOpen}
        onToggle={handleDrawerToggle}
        onWidthChange={handleDrawerWidthChange}
        vehicles={vehicles}
      />

      <div
        className="main-content"
        style={{
          marginLeft: `${drawerWidth}px`,
          transition: 'margin-left 0.1s ease'
        }}
      >
        <Mapbox drawerWidth={drawerWidth} />
        <GameControls/>
      </div>

      <footer
	  className="App-bottom-tray"
          style={{
            marginLeft: `${drawerWidth}px`,
            transition: 'margin-left 0.1s ease'
          }}
      >
      <VehicleGroup vehicles={vehicles} togglefunc={toggleSelected}/>
      </footer>
    </>
  )
}

export default App
