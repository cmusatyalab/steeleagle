import { useRef, useEffect } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css';
import { MAPBOX_TOKEN } from './config.js';
import { vehicleColor } from './mapUtils.js'

function createVehicleMarkerElement(color, selected) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  el.setAttribute('width', '34');
  el.setAttribute('height', '34');
  el.setAttribute('viewBox', '0 0 34 34');

  if (selected) {
    const ring = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    ring.setAttribute('cx', '17');
    ring.setAttribute('cy', '17');
    ring.setAttribute('r', '15');
    ring.setAttribute('fill', 'none');
    ring.setAttribute('stroke', '#ffffff');
    ring.setAttribute('stroke-width', '2');
    el.appendChild(ring);
  }

  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', 'M17 6 L26 27 L17 22 L8 27 Z');
  path.setAttribute('fill', color);
  path.setAttribute('stroke', '#ffffff');
  path.setAttribute('stroke-width', '1.5');
  path.setAttribute('stroke-linejoin', 'round');
  el.appendChild(path);

  return el;
}

function Mapbox({ selectedVehicle, vehicles, mapPanelSize, tracking, detectedObjects, mapHeight, squadList, onToggleVehicle }) {
  const mapRef = useRef()
  const mapContainerRef = useRef()
  const markerRefs = useRef([]); // To store references to all markers
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

    markerRefs.current.forEach(marker => marker.remove());
    markerRefs.current = [];
    vehicles.forEach(v => {
      const isSelected = !!(squadList && squadList.includes(v.name));
      let marker = new mapboxgl.Marker({ element: createVehicleMarkerElement(vehicleColor(v.name), isSelected), rotation: v.bearing, rotationAlignment: 'map' })
        .setLngLat([v.current.long, v.current.lat])
        .setPopup(
          new mapboxgl.Popup({ offset: 20, anchor: 'top', focusAfterOpen: false, closeButton: false, closeOnClick: false, className: 'vehicle-label-popup' })
            .setHTML(`<strong>${v.name}<br>${v.current.alt.toFixed(2)} m</strong>`)
        )
        .addTo(mapRef.current);
      marker.togglePopup();
      const markerDiv = marker.getElement();

      if (onToggleVehicle) {
        markerDiv.style.cursor = 'pointer';
        markerDiv.addEventListener('click', () => onToggleVehicle(v.name));
      }

      if (tracking && v.name === selectedVehicle) {
        mapRef.current.flyTo({
          center: [v.current.long, v.current.lat],
          //zoom: 18.03,
          essential: true, // this animation is considered essential with respect to prefers-reduced-motion
        });
      }
      markerRefs.current.push(marker);
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
        circle.setAttribute('fill', vehicleColor(d.cls));
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

  }, [vehicles, detectedObjects, squadList]);

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
