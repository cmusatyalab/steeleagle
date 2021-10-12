import React, { useState, useRef, useEffect } from 'react'
import GoogleMapReact from 'google-map-react'
import io from "socket.io-client"
import './map.css'


const LocationPin = ({tag, alt, spd, state}) => (
    <div className="pin">
        <p className="pin-text">
            Tag: {tag}<br/>
            Altitude: {alt}<br/>
            Airspeed: {spd}<br/>
            State: {state}<br/>
        </p>
    </div>
)

const defaultLocation = {
    lat: 40.41651, 
    lng: -79.94887,
}

const defaultZoom = 12;


function Map() {
    // Keep track of the drones in flight
    const [drones, setDrones] = useState([]);
    const [mapObj, setMapObj] = useState(null);
    const [mapsApi, setMapsApi] = useState(null);
    const socketRef = useRef();

    useEffect(() => {
        socketRef.current = io.connect('http://steel-eagle-dashboard.pgh.cloudapp.azurelel.cs.cmu.edu:8080');
        socketRef.current.on("update_drone_data", data => {
            updateDrones(JSON.parse(data)['drones']);
        });

        return () => socketRef.current.disconnect();
    }, []);

    const updateDrones = (newDrones) => {
        setDrones(newDrones);
    }
    
    var lineSymbol = {
        path: 'M 0,-1 0,1',
        strokeOpacity: 1,
        scale: 4
      };

    const renderLocationPins = () => {
	for (var i = 0; i < drones.length; i++) {
	    const {tag, lat, lng, alt, spd, state, plan} = drones[i];
            let nonGeodesicPolyline = new mapsApi.Polyline({
	      path: plan,
              geodesic: false,
              strokeColor: '#2596be',
              strokeWeight: 3,
              strokeOpacity: 0,
              icons: [{
                icon: lineSymbol,
                offset: '0',
                repeat: '20px'
              }],
            });
	    nonGeodesicPolyline.setMap(mapObj);
	}
        return drones.map((drone, index) => {
            const {tag, lat, lng, alt, spd, state, plan} = drone
            return (
                <LocationPin
                    lat={lat}
                    lng={lng}
                    tag={tag}
		    alt={alt}
		    spd={spd}
		    state={state}
                />
            )
        })
    }

    const setMaps = (map, maps) => {
	setMapObj(map);
	setMapsApi(maps);
    }

    return (
        <div className="map">
            <h2 className="map-h2">Drone Locator</h2>
            <div className="google-map">
                <GoogleMapReact
                bootstrapURLKeys={{ key: 'AIzaSyApnLUQeyT4AEfpEa6rL5THv0XyHxOFmaY' }}
                defaultCenter={defaultLocation}
                defaultZoom={defaultZoom}
	        yesIWantToUseGoogleMapApiInternals
	    	onGoogleApiLoaded={({map, maps}) => setMaps(map, maps)}>
                    {renderLocationPins()}
                </GoogleMapReact>
            </div>
        </div>
    )
}

export default Map
