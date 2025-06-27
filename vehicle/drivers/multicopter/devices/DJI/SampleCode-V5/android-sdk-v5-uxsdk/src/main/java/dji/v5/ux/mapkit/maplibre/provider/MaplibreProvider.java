package dji.v5.ux.mapkit.maplibre.provider;

import android.content.Context;
import android.view.Gravity;

import com.mapbox.mapboxsdk.Mapbox;
import com.mapbox.mapboxsdk.WellKnownTileServer;
import com.mapbox.mapboxsdk.maps.MapboxMapOptions;

import androidx.annotation.NonNull;
import dji.v5.ux.mapkit.core.Mapkit;
import dji.v5.ux.mapkit.core.MapkitOptions;
import dji.v5.ux.mapkit.core.maps.DJIMapViewInternal;
import dji.v5.ux.mapkit.core.places.IInternalPlacesClient;
import dji.v5.ux.mapkit.core.providers.MapProvider;
import dji.v5.ux.mapkit.maplibre.map.MaplibreMapView;
import dji.v5.ux.mapkit.maplibre.place.MaplibrePlaceDelegate;

import static dji.v5.ux.mapkit.core.Mapkit.MapProviderConstant.MAPLIBRE_MAP_PROVIDER;


public class MaplibreProvider extends MapProvider {

    public MaplibreProvider() {
        providerType = MAPLIBRE_MAP_PROVIDER;
    }

    @Override
    protected DJIMapViewInternal requestMapView(@NonNull Context context,
                                                @NonNull MapkitOptions mapkitOptions) {
        DJIMapViewInternal mapView = null;

        final int mapType = mapkitOptions.getMapType();
        Mapkit.mapType(mapType);
        Mapkit.mapProvider(providerType);
        Mapbox.getInstance(context.getApplicationContext(), Mapkit.getMapboxAccessToken(), WellKnownTileServer.Mapbox);
        MapboxMapOptions options = MapboxMapOptions.createFromAttributes(context);
        options.textureMode(true);
        options.attributionGravity(Gravity.BOTTOM | Gravity.RIGHT);
        options.logoGravity(Gravity.BOTTOM | Gravity.RIGHT);
        options.logoMargins(new int[]{0, 0, 75, 12});
        mapView = new MaplibreMapView(context, options);

        return mapView;
    }

    @Override
    protected IInternalPlacesClient requestGeocodingClient(Context context, MapkitOptions mapkitOptions) {
        IInternalPlacesClient client = null;
        Mapkit.geocodingProvider(getProviderType());
        client = new MaplibrePlaceDelegate();
        return client;
    }
}
