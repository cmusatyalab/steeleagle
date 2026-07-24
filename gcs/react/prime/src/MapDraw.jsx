import { useState, useRef, useEffect, useMemo } from 'react';
import mapboxgl from 'mapbox-gl';
import MapboxDraw from '@mapbox/mapbox-gl-draw';
import 'mapbox-gl/dist/mapbox-gl.css';
import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';
import { MAPBOX_TOKEN } from './config.js';
import { Button } from 'primereact/button';
import { Dropdown } from 'primereact/dropdown';
import { featuresToGeoJson, featuresToKml, parseImportFile, bboxFromFeature } from './mapUtils.js';
import FeatureList from './FeatureList.jsx';

const STYLE_URLS = {
    streets: 'mapbox://styles/mapbox/standard',
    satellite: 'mapbox://styles/mapbox/satellite-streets-v12',
};

const STYLE_OPTIONS = [
    { label: 'Streets', value: 'streets' },
    { label: 'Satellite', value: 'satellite' },
];

const DRAW_STYLES = [
    {
        id: 'gl-draw-polygon-fill',
        type: 'fill',
        filter: ['all', ['==', '$type', 'Polygon']],
        paint: {
            'fill-color': ['case', ['==', ['get', 'active'], 'true'], '#fbb03b', '#3bb2d0'],
            'fill-opacity': 0.2,
        },
    },
    {
        id: 'gl-draw-lines',
        type: 'line',
        filter: ['any', ['==', '$type', 'LineString'], ['==', '$type', 'Polygon']],
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
            'line-color': ['case', ['==', ['get', 'active'], 'true'], '#fbb03b', '#3bb2d0'],
            'line-width': 3,
        },
    },
    {
        id: 'gl-draw-point-outer',
        type: 'circle',
        filter: ['all', ['==', '$type', 'Point'], ['==', 'meta', 'feature']],
        paint: {
            'circle-radius': ['case', ['==', ['get', 'active'], 'true'], 8, 6],
            'circle-color': '#fff',
        },
    },
    {
        id: 'gl-draw-point-inner',
        type: 'circle',
        filter: ['all', ['==', '$type', 'Point'], ['==', 'meta', 'feature']],
        paint: {
            'circle-radius': ['case', ['==', ['get', 'active'], 'true'], 6, 4],
            'circle-color': ['case', ['==', ['get', 'active'], 'true'], '#fbb03b', '#3bb2d0'],
        },
    },
    {
        id: 'gl-draw-vertex-outer',
        type: 'circle',
        filter: ['all', ['==', '$type', 'Point'], ['==', 'meta', 'vertex'], ['!=', 'mode', 'simple_select']],
        paint: {
            'circle-radius': ['case', ['==', ['get', 'active'], 'true'], 10, 7],
            'circle-color': '#fff',
        },
    },
    {
        id: 'gl-draw-vertex-inner',
        type: 'circle',
        filter: ['all', ['==', '$type', 'Point'], ['==', 'meta', 'vertex'], ['!=', 'mode', 'simple_select']],
        paint: {
            'circle-radius': ['case', ['==', ['get', 'active'], 'true'], 7, 5],
            'circle-color': '#fbb03b',
        },
    },
    {
        id: 'gl-draw-midpoint',
        type: 'circle',
        filter: ['all', ['==', 'meta', 'midpoint']],
        paint: { 'circle-radius': 4, 'circle-color': '#fbb03b' },
    },
];

function MapDraw({ features, setFeatures, toast }) {
    const mapRef = useRef();
    const mapContainerRef = useRef();
    const draw = useRef();
    const numFeaturesRef = useRef(0);
    const importFileRef = useRef(null);
    const isFirstStyleEffect = useRef(true);

    const [selectedFeatureId, setSelectedFeatureId] = useState(null);
    const [mapStyle, setMapStyle] = useState('streets');

    const hasFeatures = useMemo(() => {
        try { return JSON.parse(features).features.length > 0; } catch { return false; }
    }, [features]);

    const featureArray = useMemo(() => {
        try { return JSON.parse(features).features ?? []; } catch { return []; }
    }, [features]);

    useEffect(() => {
        mapboxgl.accessToken = `${MAPBOX_TOKEN}`;
        mapRef.current = new mapboxgl.Map({
            container: mapContainerRef.current,
            style: 'mapbox://styles/mapbox/standard',
            center: [-79.94299, 40.44353],
            zoom: 13.03,
            config: {
                basemap: {
                    lightPreset: 'day',
                    showPedestrianRoads: false,
                    showPointOfInterestLabels: false,
                    showTransitLabels: false,
                    showAdminBoundaries: false,
                    font: 'Montserrat',
                }
            },
        });

        mapRef.current.on('load', () => {
            mapRef.current.addControl(new mapboxgl.NavigationControl());
        });

        mapRef.current.on('style.load', () => {
            mapRef.current.addSource('mapbox-dem', {
                type: 'raster-dem',
                url: 'mapbox://mapbox.mapbox-terrain-dem-v1',
                tileSize: 512,
                maxzoom: 14,
            });
            mapRef.current.setTerrain({ source: 'mapbox-dem', exaggeration: 1.0 });
        });

        draw.current = new MapboxDraw({ displayControlsDefault: true, defaultMode: 'draw_polygon', styles: DRAW_STYLES });
        mapRef.current.addControl(draw.current);

        function updateFeatures(e) {
            let temp = draw.current.get(e.features[0].id);
            temp.id = e.features[0].geometry.type + '-' + numFeaturesRef.current++;
            draw.current.add(temp);
            draw.current.delete(e.features[0].id);
            setFeatures(JSON.stringify(draw.current.getAll()));
        }

        function deleteFeature(e) {
            draw.current.delete(e.features[0].id);
            setFeatures(JSON.stringify(draw.current.getAll()));
            setSelectedFeatureId(null);
        }

        function selectFeature(e) {
            if (e.features && e.features.length > 0) {
                setSelectedFeatureId(e.features[0].id);
            } else {
                setSelectedFeatureId(null);
            }
        }

        mapRef.current.on('draw.create', updateFeatures);
        mapRef.current.on('draw.delete', deleteFeature);
        mapRef.current.on('draw.update', updateFeatures);
        mapRef.current.on('draw.selectionchange', selectFeature);

        const timer = setTimeout(() => { mapRef.current?.resize(); }, 100);
        const ro = new ResizeObserver(() => { mapRef.current?.resize(); });
        ro.observe(mapContainerRef.current);

        return () => { clearTimeout(timer); ro.disconnect(); mapRef.current.remove(); };
    }, []);

    useEffect(() => {
        if (!mapRef.current) return;
        if (isFirstStyleEffect.current) { isFirstStyleEffect.current = false; return; }
        mapRef.current.setStyle(STYLE_URLS[mapStyle]);
    }, [mapStyle]);

    function handleRenameFeature(id, name) {
        const feat = draw.current?.get(id);
        if (!feat) return;
        feat.properties = { ...(feat.properties || {}), name };
        draw.current.add(feat);
        setFeatures(JSON.stringify(draw.current.getAll()));
    }

    function handleSelectFeature(id) {
        const feature = draw.current?.get(id);
        if (!feature) return;
        draw.current.changeMode('simple_select', { featureIds: [id] });
        setSelectedFeatureId(id);
        try {
            const bbox = bboxFromFeature(feature);
            mapRef.current?.fitBounds(bbox, { padding: 60, maxZoom: 18 });
        } catch (_) {}
    }

    function handleDeleteFeature(id) {
        draw.current?.delete(id);
        setFeatures(JSON.stringify(draw.current.getAll()));
        if (selectedFeatureId === id) {
            setSelectedFeatureId(null);
        }
    }

    function handleExportGeoJson() {
        const blob = new Blob([featuresToGeoJson(features)], { type: 'application/geo+json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'map-features.geojson';
        a.click();
        URL.revokeObjectURL(url);
    }

    function handleExportKml() {
        const blob = new Blob([featuresToKml(features)], { type: 'application/vnd.google-earth.kml+xml' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'map-features.kml';
        a.click();
        URL.revokeObjectURL(url);
    }

    async function handleImport(file) {
        if (!file) return;
        try {
            const text = await file.text();
            const fc = parseImportFile(file.name, text);
            draw.current.deleteAll();
            draw.current.set(fc);
            numFeaturesRef.current = fc.features.length;
            setFeatures(JSON.stringify(draw.current.getAll()));
        } catch (e) {
            toast.current.show({ severity: 'error', summary: 'Import failed', detail: e.message });
        } finally {
            if (importFileRef.current) importFileRef.current.value = '';
        }
    }

    return (
        <div className="flex flex-column" style={{ height: '100%' }}>
            <div className="flex gap-2 align-items-center p-2" style={{ borderBottom: '1px solid #2a3a4a' }}>
                <input
                    ref={importFileRef}
                    type="file"
                    accept=".kml,.geojson,.json"
                    style={{ display: 'none' }}
                    onChange={e => handleImport(e.target.files[0])}
                />
                <Button
                    label="Import"
                    icon="pi pi-upload"
                    size="small"
                    outlined
                    onClick={() => importFileRef.current?.click()}
                />
                <Button
                    label="Export GeoJSON"
                    icon="pi pi-file"
                    size="small"
                    outlined
                    disabled={!hasFeatures}
                    onClick={handleExportGeoJson}
                />
                <Button
                    label="Export KML"
                    icon="pi pi-file-export"
                    size="small"
                    outlined
                    disabled={!hasFeatures}
                    onClick={handleExportKml}
                />
                <Dropdown
                    value={mapStyle}
                    options={STYLE_OPTIONS}
                    onChange={e => setMapStyle(e.value)}
                    className="p-inputtext-sm"
                    style={{ width: 130 }}
                />
            </div>
            <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
                <FeatureList
                    features={featureArray}
                    selectedFeatureId={selectedFeatureId}
                    onSelect={handleSelectFeature}
                    onDelete={handleDeleteFeature}
                    onRename={handleRenameFeature}
                />
                <div id="map-container" ref={mapContainerRef} style={{ flex: 1 }} />
            </div>
        </div>
    );
}

export default MapDraw;
