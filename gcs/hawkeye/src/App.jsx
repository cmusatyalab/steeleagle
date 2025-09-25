import { useState } from 'react'
import { useRef, useEffect } from 'react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { fas } from '@fortawesome/free-solid-svg-icons'
import { library } from '@fortawesome/fontawesome-svg-core'

import Mapbox from './Mapbox.jsx'
import Drawer from './Drawer.jsx'

import './App.css'

library.add(fas)

function App() {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerWidth, setDrawerWidth] = useState(0);

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
          transition: 'margin-left 0.3s ease'
        }}
      >
        <Mapbox drawerWidth={drawerWidth} />
      </div>
      
      <footer className="App-bottom-tray"></footer>
    </>
  )
}

export default App
