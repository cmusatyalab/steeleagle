import { useState, useRef, useEffect } from 'react';
import CameraFeedCard from './CameraFeedCard.jsx';
import './Drawer.css';

function Drawer({ isOpen, onToggle, onWidthChange, vehicles }) {
  const [isDragging, setIsDragging] = useState(false);
  const [drawerWidth, setDrawerWidth] = useState(320); // Default width
  const [cardWidth, setCardWidth] = useState(288); // Default: 18rem = 288px
  const drawerRef = useRef(null);
  const dragHandleRef = useRef(null);
  const cardRef = useRef(null);
  const startXRef = useRef(0);
  const startWidthRef = useRef(0);

  const maxWidth = 600;

  // Measure the camera card width when component mounts
  useEffect(() => {
    const measureCardWidth = () => {
      // Look for the card element in the DOM
      const cardElement = document.querySelector('.card');
      if (cardElement) {
        const rect = cardElement.getBoundingClientRect();
        const measuredWidth = Math.ceil(rect.width) + 40; // Add padding (20px on each side)
        setCardWidth(measuredWidth);

        // Update drawer width if current width is smaller than card width
        if (drawerWidth < measuredWidth) {
          setDrawerWidth(measuredWidth);
        }
      }
    };

    // Measure after a short delay to ensure the card is rendered
    const timer = setTimeout(measureCardWidth, 100);

    // Also measure on window resize
    window.addEventListener('resize', measureCardWidth);

    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', measureCardWidth);
    };
  }, [drawerWidth]);

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
    const newWidth = Math.min(maxWidth, Math.max(cardWidth, startWidthRef.current + deltaX));

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
  }, [isDragging, drawerWidth, cardWidth]);

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
              {vehicles.filter(item => item.selected).map((vehicle) => (
            <CameraFeedCard key={vehicle.name} ref={cardRef} data={vehicle} />
              ))}
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
