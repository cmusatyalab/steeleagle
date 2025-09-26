import { useState } from 'react'
import { useRef, useEffect } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css';

function Mapbox({ drawerWidth }) {
  const mapRef = useRef()
  const mapContainerRef = useRef()
 
  useEffect(() => {
    mapboxgl.accessToken = 'pk.eyJ1IjoibWloaXJiYWxhIiwiYSI6ImNtZnB4c29yajBtNGcybXEyOW45dmYyY24ifQ.hjJrPxoZ4Qoi6rqBIYkXVQ'
    
    mapRef.current = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: 'mapbox://styles/mapbox/standard',
      center: [0, 0], // Center the map on longitude 0, latitude 0
      zoom: 2, // Set an appropriate zoom level to see the whole globe
      config: {
        basemap: {
          theme: 'monochrome',
          lightPreset: 'night',
          showPointOfInterestLabels: false
        }
      },
    });
    
    mapRef.current.on('style.load', () => {
      mapRef.current.addSource('mapbox-dem', {
        type: 'raster-dem',
        url: 'mapbox://mapbox.mapbox-terrain-dem-v1',
        tileSize: 512,
        maxzoom: 14
      });
      mapRef.current.setTerrain({ source: 'mapbox-dem', exaggeration: 1.0 });
      mapRef.current.addControl(new mapboxgl.NavigationControl());
      
      // Ensure the map is properly resized after container is ready
      mapRef.current.resize();
    });

    // Add a small delay to ensure container is fully rendered
    const timer = setTimeout(() => {
      if (mapRef.current) {
        mapRef.current.resize();
      }
    }, 100);

    return () => {
      clearTimeout(timer);
      mapRef.current.remove();
    }
  }, [])

  // Handle drawer width changes
  useEffect(() => {
    if (mapRef.current) {
      // Small delay to ensure smooth transition
      const resizeTimer = setTimeout(() => {
        mapRef.current.resize();
      }, 300);
      
      return () => clearTimeout(resizeTimer);
    }
  }, [drawerWidth]);
  
  return (
    <>
      <div id='map-container' ref={mapContainerRef}/>
    </>
  )
}

export default Mapbox
