import { useRef, useEffect } from 'react'
import mapboxgl from 'mapbox-gl'
import 'mapbox-gl/dist/mapbox-gl.css';
import { MAPBOX_TOKEN } from './config.js';
import { vehicleColor, isVehicleDisconnected, vehicleStatus, vehicleStatusMapColor, vehicleStatusTextColor } from './mapUtils.js'
import { vehicleControlGroupDigits } from './squadUtils.js'

// No ring/badge here anymore -- the whole marker element rotates with
// `rotation: v.bearing` below, so anything drawn on it would visibly spin
// as the vehicle turns. Status is carried by fill color alone, which
// rotating doesn't affect. Quick-squad membership moved to the popup
// label instead (see the .setHTML call below).
function createVehicleMarkerElement(color) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  el.setAttribute('width', '34');
  el.setAttribute('height', '34');
  el.setAttribute('viewBox', '0 0 34 34');

  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', 'M17 6 L26 27 L17 22 L8 27 Z');
  // Assigned via style rather than the fill attribute so the CSS
  // var(--...) status color resolves against the page's theme tokens.
  path.style.fill = color;
  path.setAttribute('stroke', '#ffffff');
  path.setAttribute('stroke-width', '1.5');
  path.setAttribute('stroke-linejoin', 'round');
  el.appendChild(path);

  return el;
}

function Mapbox({ selectedVehicle, vehicles, mapPanelSize, tracking, detectedObjects, mapHeight, squadList, onToggleVehicle, controlGroups }) {
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

    // The map container's width changes whenever the squad sidebar
    // collapses/expands (or the window resizes). Mapbox GL doesn't detect
    // that on its own -- it only repaints the canvas at whatever size it
    // measured on creation -- so without this the map stays the old size
    // and the freed-up space just shows as empty grey padding.
    const resizeObserver = new ResizeObserver(() => {
      if (mapRef.current) {
        mapRef.current.resize();
      }
    });
    resizeObserver.observe(mapContainerRef.current);

    return () => {
      clearTimeout(timer);
      resizeObserver.disconnect();
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
      const status = vehicleStatus(isVehicleDisconnected(v), isSelected);
      const groupDigits = vehicleControlGroupDigits(controlGroups ?? {}, v.name);
      const chipsHtml = groupDigits.map((d) => `<span class="squad-chip">${d}</span>`).join('');
      let marker = new mapboxgl.Marker({ element: createVehicleMarkerElement(vehicleStatusMapColor(status)), rotation: v.bearing, rotationAlignment: 'map' })
        .setLngLat([v.current.long, v.current.lat])
        .setPopup(
          new mapboxgl.Popup({ offset: 20, anchor: 'top', focusAfterOpen: false, closeButton: false, closeOnClick: false, className: 'vehicle-label-popup' })
            .setHTML(`<strong style="color:${vehicleStatusTextColor(status)}">${chipsHtml}${v.name}<br>${v.current.alt.toFixed(2)} m</strong>`)
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

  }, [vehicles, detectedObjects, squadList, controlGroups]);

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
