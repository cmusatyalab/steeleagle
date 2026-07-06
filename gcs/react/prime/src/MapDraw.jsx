import { useState, useRef, useEffect, useMemo } from 'react';
import mapboxgl from 'mapbox-gl';
import MapboxDraw from '@mapbox/mapbox-gl-draw';
import 'mapbox-gl/dist/mapbox-gl.css';
import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';
import { MAPBOX_TOKEN } from './config.js';
import { InputText } from 'primereact/inputtext';
import { Button } from 'primereact/button';
import { Dropdown } from 'primereact/dropdown';
import { featuresToGeoJson, featuresToKml, parseImportFile } from './mapUtils.js';

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

    const [selectedFeatureId, setSelectedFeatureId] = useState(null);
    const [nameInput, setNameInput] = useState('');
    const [mapStyle, setMapStyle] = useState('streets');

    const hasFeatures = useMemo(() => {
        try { return JSON.parse(features).features.length > 0; } catch { return false; }
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
                const fid = e.features[0].id;
                setSelectedFeatureId(fid);
                const feat = draw.current.get(fid);
                setNameInput(feat?.properties?.name || '');
            } else {
                setSelectedFeatureId(null);
                setNameInput('');
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
        mapRef.current.setStyle(STYLE_URLS[mapStyle]);
    }, [mapStyle]);

    function applyName() {
        if (!selectedFeatureId) return;
        const feat = draw.current.get(selectedFeatureId);
        if (!feat) return;
        feat.properties = { ...(feat.properties || {}), name: nameInput };
        draw.current.add(feat);
        setFeatures(JSON.stringify(draw.current.getAll()));
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
                {selectedFeatureId && (
                    <div className="flex gap-2 align-items-center" style={{ marginLeft: 'auto' }}>
                        <label className="text-sm">Area name:</label>
                        <InputText
                            value={nameInput}
                            onChange={e => setNameInput(e.target.value)}
                            placeholder="e.g. AreaB"
                            className="p-inputtext-sm"
                            style={{ width: 160 }}
                            onKeyDown={e => { if (e.key === 'Enter') applyName(); }}
                        />
                        <Button label="Set" size="small" onClick={applyName} />
                    </div>
                )}
            </div>
            <div id="map-container" ref={mapContainerRef} style={{ flex: 1 }} />
        </div>
    );
}

export default MapDraw;
