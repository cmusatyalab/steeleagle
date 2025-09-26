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
import 'bootstrap/dist/css/bootstrap.min.css';

library.add(fas)

function App() {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerWidth, setDrawerWidth] = useState(0);
  const [selectedList] = useState(['diderot', 'sparrow', 'condor','mihir', ])

  const handleDrawerToggle = () => {
    setIsDrawerOpen(!isDrawerOpen);
  };

  const handleDrawerWidthChange = (width) => {
    setDrawerWidth(width);
  };

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
      <VehicleGroup selectedList={selectedList}/>
      </footer>
    </>
  )
}

export default App
