import { useState, useRef, useEffect } from 'react';
import CameraFeedCard from './CameraFeedCard.jsx';
import './Drawer.css';

function Drawer({ isOpen, onToggle, onWidthChange }) {
  const [isDragging, setIsDragging] = useState(false);
  const [drawerWidth, setDrawerWidth] = useState(320); // Default width
  const drawerRef = useRef(null);
  const dragHandleRef = useRef(null);
  const startXRef = useRef(0);
  const startWidthRef = useRef(0);

  const minWidth = 200;
  const maxWidth = 600;

  const handleMouseDown = (e) => {
    setIsDragging(true);
    startXRef.current = e.clientX;
    startWidthRef.current = drawerWidth;
    document.body.style.cursor = 'ew-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  };

  const handleMouseMove = (e) => {
    if (!isDragging) return;
    
    const deltaX = e.clientX - startXRef.current;
    const newWidth = Math.min(maxWidth, Math.max(minWidth, startWidthRef.current + deltaX));
    
    setDrawerWidth(newWidth);
    onWidthChange(newWidth);
  };

  const handleMouseUp = () => {
    setIsDragging(false);
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  };

  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, drawerWidth]);

  // Notify parent of width changes
  useEffect(() => {
    onWidthChange(isOpen ? drawerWidth : 0);
  }, [isOpen, drawerWidth, onWidthChange]);

  return (
    <>      
      {/* Drawer */}
      <div 
        ref={drawerRef}
        className={`drawer ${isOpen ? 'open' : ''}`}
        style={{ width: `${drawerWidth}px` }}
      >
        <div className="drawer-content">
          <div className="drawer-section">
            <h4>Camera Feeds</h4>
            <ul className="drawer-list">
	    <CameraFeedCard/>
            </ul>
          </div>
        </div>
        
        {/* Resize handle */}
        <div 
          ref={dragHandleRef}
          className="drawer-resize-handle"
          onMouseDown={handleMouseDown}
        />
      </div>
    </>
  );
}

export default Drawer;
