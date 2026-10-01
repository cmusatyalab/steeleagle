import { useState } from 'react'
import { useRef, useEffect } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css';
import { MAPBOX_TOKEN } from './config.js';
import ColorHash from 'color-hash'
import { syncVehicleMarkers } from './vehicleMarkers.js';

function Mapbox({ selectedVehicle, vehicles, mapPanelSize, tracking, detectedObjects, mapHeight }) {
  const mapRef = useRef()
  const mapContainerRef = useRef()
  const [currentLoc, setCurrentLoc] = useState(null);
  const markerRefs = useRef([]); // To store references to all markers
  var colorHash = new ColorHash();
  useEffect(() => {
    mapboxgl.accessToken = `${MAPBOX_TOKEN}`;

    mapRef.current = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: 'mapbox://styles/mapbox/standard',
      center: [-79.94299, 40.44353],
      zoom: 13.03,
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

    syncVehicleMarkers(mapRef.current, vehicles, markerRefs);
    vehicles.forEach(v => {
      if (tracking && v.name === selectedVehicle && Number.isFinite(v.current?.long) && Number.isFinite(v.current?.lat)) {
        mapRef.current.flyTo({
          center: [v.current.long, v.current.lat],
          //zoom: 18.03,
          essential: true, // this animation is considered essential with respect to prefers-reduced-motion
        });
      }
    });

    if (detectedObjects != null) {
      detectedObjects.forEach(d => {
        // Create the SVG element
        const el = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        el.setAttribute('width', '16');
        el.setAttribute('height', '16');
        el.setAttribute('viewBox', '0 0 16 16');

        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('cx', '8');
        circle.setAttribute('cy', '8');
        circle.setAttribute('r', '7');
        circle.setAttribute('fill', colorHash.hex(d.cls));
        circle.setAttribute('stroke', '#fff');
        circle.setAttribute('stroke-width', '2');

        el.appendChild(circle);

        let marker = new mapboxgl.Marker({ element: el })
          .setLngLat([d.longitude, d.latitude])
          .setPopup(new mapboxgl.Popup({ focusAfterOpen: false }).setHTML(`<strong style="color:black">${d.id} (${d.confidence.toFixed(2) * 100}%)</strong><img src="${d.link}" style="width:100%;height:auto;margin-top:5px;" />`))
          .addTo(mapRef.current);
        const markerDiv = marker.getElement();

        markerDiv.addEventListener('mouseenter', () => marker.togglePopup());
        markerDiv.addEventListener('mouseleave', () => marker.togglePopup());
        markerRefs.current.push(marker);
      });
    }

  }, [vehicles, detectedObjects]);

  useEffect(() => {
    let v = vehicles.find(v => v.name === selectedVehicle);
    if (v) {
      mapRef.current.flyTo({
        center: [v.current.long, v.current.lat],
        //zoom: 18.03,
        essential: true, // this animation is considered essential with respect to prefers-reduced-motion
      });
    }


  }, [selectedVehicle]);

  return (
    <div id='map-container' ref={mapContainerRef} style={{ width: '100%', height: mapHeight || '20rem' }} />
  )
}

export default Mapbox
