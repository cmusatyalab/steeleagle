import mapboxgl from 'mapbox-gl';
import ColorHash from 'color-hash';

const colorHash = new ColorHash();

function hasFix(vehicle) {
    const lng = vehicle?.current?.long;
    const lat = vehicle?.current?.lat;
    return Number.isFinite(lng) && Number.isFinite(lat);
}

// Place vehicle markers on the Mapbox GL map.
// Same design as in the Control page. 
export function syncVehicleMarkers(map, vehicles, markerRefs) {
    markerRefs.current.forEach((marker) => marker.remove());
    markerRefs.current = [];
    if (!map) return;

    for (const vehicle of vehicles || []) {
        if (!hasFix(vehicle)) continue;
        const { long: lng, lat, alt } = vehicle.current;
        const altLabel = Number.isFinite(alt) ? `${alt.toFixed(2)} m` : 'n/a';
        const marker = new mapboxgl.Marker({
            color: colorHash.hex(vehicle.name),
            rotation: vehicle.bearing ?? 0,
            rotationAlignment: 'map',
        })
            .setLngLat([lng, lat])
            .setPopup(
                new mapboxgl.Popup({ focusAfterOpen: false }).setHTML(
                    `<strong style="color:black">${vehicle.name} (${altLabel})</strong>`
                )
            )
            .addTo(map);

        marker.togglePopup();
        const markerDiv = marker.getElement();
        markerDiv.addEventListener('mouseenter', () => marker.togglePopup());
        markerDiv.addEventListener('mouseleave', () => marker.togglePopup());
        markerRefs.current.push(marker);
    }
}
