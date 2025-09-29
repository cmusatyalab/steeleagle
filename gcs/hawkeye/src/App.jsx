import { useState } from 'react'
import { useRef, useEffect } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { fas } from '@fortawesome/free-solid-svg-icons'
import { library } from '@fortawesome/fontawesome-svg-core'

import Mapbox from './Mapbox.jsx'
import Drawer from './Drawer.jsx'
import VehicleGroup from './VehicleGroup.jsx'

import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css'

library.add(fas)

var adjective = ["Steel", "Iron", "Brass","Golden", "Liquid", "Solid", "Adamantium", "Titantium"]
var object = ["Eagle", "Hawk", "Sparrow", "Condor", "Parrot", "Lark", "Falcon"]
var models = ["Parrot ANAFI", "Generic MAVLink", "Ascent Systems Spirit", "DJI Mini 4 Pro"]

function getRandomInt(min, max) {
  const minCeiled = Math.ceil(min);
  const maxFloored = Math.floor(max);
  return Math.floor(Math.random() * (maxFloored - minCeiled) + minCeiled); // The maximum is exclusive and the minimum is inclusive
}

function getRandomName() {
  return adjective[Math.floor(Math.random() * adjective.length)] + " " + object[Math.floor(Math.random() * object.length)];
}

function generateVehicleData() {
  var vehicles = [];
  var number = getRandomInt(1,10);
  for (var i=0; i< number; i++) {
    vehicles[i] = ({ name: getRandomName(), model: models[Math.floor(Math.random() * models.length)], battery: getRandomInt(0,100), sats: getRandomInt(0,25), task: Math.random() >0.5 ? "idle" : "tracking" , last_updated: getRandomInt(0,30)})
  }
  return vehicles;
}

function App() {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerWidth, setDrawerWidth] = useState(0);
  const [selectedList, updateSelectedVehicles] = useState([])
  const [vehicles] = useState(generateVehicleData());
  const handleDrawerToggle = () => {
    setIsDrawerOpen(!isDrawerOpen);
  };

  const handleDrawerWidthChange = (width) => {
    setDrawerWidth(width);
  };

    function selectVehicle(index) {
    alert(selectedList);
  }



  return (
    <>
      <nav className="App-header">
        <div className="nav-left">
          <button className="nav-hamburger" onClick={handleDrawerToggle}>
            <FontAwesomeIcon icon={`fas-solid ${isDrawerOpen ? "fa-eye-slash" : "fa-eye"}`} />
          </button>
          <span className="nav-title">Hawkeye</span>
        </div>
      </nav>

      <Drawer
        isOpen={isDrawerOpen}
        onToggle={handleDrawerToggle}
        onWidthChange={handleDrawerWidthChange}
      />

      <div
        className="main-content"
        style={{
          marginLeft: `${drawerWidth}px`,
          transition: 'margin-left 0.1s ease'
        }}
      >
        <Mapbox drawerWidth={drawerWidth} />
      </div>

      <footer
	  className="App-bottom-tray"
          style={{
            marginLeft: `${drawerWidth}px`,
            transition: 'margin-left 0.1s ease'
          }}
      >
      <VehicleGroup selectedList={selectedList} vehicles={vehicles} onClick={selectVehicle}/>
      </footer>
    </>
  )
}

export default App
