import { useState } from 'react'
import { useRef, useEffect } from 'react'
import mapboxgl from 'mapbox-gl';
import MapboxDraw from '@mapbox/mapbox-gl-draw';
import 'mapbox-gl/dist/mapbox-gl.css';
import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';
import { MAPBOX_TOKEN } from './config.js';
import ColorHash from 'color-hash'

function MapDraw({ features, setFeatures }) {
    const mapRef = useRef();
    const mapContainerRef = useRef();
    const draw = useRef();
    let numFeatures = 0;

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
                    lightPreset: "day",
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

        draw.current = new MapboxDraw({
            displayControlsDefault: true,
            defaultMode: 'draw_polygon',

        });
        mapRef.current.addControl(draw.current);

        mapRef.current.on('draw.create', updateFeatures);
        mapRef.current.on('draw.delete', deleteFeature);
        mapRef.current.on('draw.update', updateFeatures);

        function updateFeatures(e) {
            let temp = draw.current.get(e.features[0].id);
            temp.id = e.features[0].geometry.type + "-" + numFeatures++;
            draw.current.add(temp);
            draw.current.delete(e.features[0].id);
            const data = draw.current.getAll();
            setFeatures(JSON.stringify(data));

        }

        function deleteFeature(e) {
            draw.current.delete(e.features[0].id);
            const data = draw.current.getAll();
            setFeatures(JSON.stringify(data));

        }



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


    return (
        <>
            <div className="flex flex-column flex-wrap align-content-center"></div>
            <div id='map-container' ref={mapContainerRef} />
        </>
    )
}

export default MapDraw
