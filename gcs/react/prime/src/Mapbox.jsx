import { useState } from 'react'
import { useRef, useEffect } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css';
import { MAPBOX_TOKEN } from './config.js';
import ColorHash from 'color-hash'

function Mapbox({ selectedVehicle, vehicles, mapPanelSize, tracking }) {
  const mapRef = useRef()
  const mapContainerRef = useRef()
  const [currentLoc, setCurrentLoc] = useState(null);
  const markerRefs = useRef([]); // To store references to all markers
  var colorHash = new ColorHash();
  if (tracking === "On") {
    tracking = true;
  }
  else {
    tracking = false;
  }
  useEffect(() => {
    mapboxgl.accessToken = `${MAPBOX_TOKEN}`;

    mapRef.current = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: 'mapbox://styles/mapbox/standard',
      center: [-79.94299, 40.44353], // Center the map on longitude 0, latitude 0
      zoom: 13.03, // Set an appropriate zoom level to see the whole globe
      config: {
        basemap: {
          lightPreset: "dusk",
          showPedestrianRoads: false,
          showPointOfInterestLabels: false,
          showTransitLabels: false,
          showAdminBoundaries: false,
          font: "Montserrat",
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
  }, []);

  // Handle drawer width changes
  useEffect(() => {
    if (mapRef.current) {
      // Small delay to ensure smooth transition
      const resizeTimer = setTimeout(() => {
        mapRef.current.resize();
      }, 100);

      return () => clearTimeout(resizeTimer);
    }
  }, [mapPanelSize]);


  useEffect(() => {

    markerRefs.current.forEach(marker => marker.remove());
    markerRefs.current = [];
    vehicles.forEach(v => {
      let marker = new mapboxgl.Marker({ "color": colorHash.hex(v.name), rotation: v.bearing, rotationAlignment: 'map'})
        .setLngLat([v.current.long, v.current.lat])
        .setPopup(new mapboxgl.Popup().setHTML(`<p style="color:black">${v.name}</p>`)) // add popup
        .addTo(mapRef.current);
      if (tracking && v.name === selectedVehicle) {
        mapRef.current.flyTo({
          center: [v.current.long, v.current.lat],
          zoom: 18.03,
          essential: true, // this animation is considered essential with respect to prefers-reduced-motion
        });
      }
      markerRefs.current.push(marker);
    });

  }, [vehicles]);

  useEffect(() => {
    let v = vehicles.find(v => v.name === selectedVehicle);
    if (v) {
      mapRef.current.flyTo({
        center: [v.current.long, v.current.lat],
        zoom: 18.03,
        essential: true, // this animation is considered essential with respect to prefers-reduced-motion
      });
    }


  }, [selectedVehicle]);

  return (
    <>
      <div id='map-container' ref={mapContainerRef} />
    </>
  )
}

export default Mapbox
