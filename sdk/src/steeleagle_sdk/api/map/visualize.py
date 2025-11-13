import logging
import folium
from folium.plugins import MousePosition, MeasureControl, Fullscreen

logger = logging.getLogger(__name__)

def visualize(raw_map, geopoints_map, out_file="map.html"):
    all_latlons = []
    m = folium.Map(location=(0, 0), zoom_start=2, control_scale=True, tiles="OpenStreetMap", max_zoom=22)

    Fullscreen().add_to(m)
    MeasureControl(position="topleft", primary_length_unit="meters").add_to(m)
    MousePosition(
        position="bottomright",
        separator=" | ",
        empty_string="",
        lng_first=False,  # show as lat, lon
        num_digits=6,
        prefix="Cursor (lat, lon):"
    ).add_to(m)

    # Draw raw areas (blue)
    for area, raw in raw_map.items():
        # raw is GeoPoints of (lon, lat); convert to (lat, lon)
        coords_latlon = [(lat, lon) for lon, lat in raw]
        all_latlons.extend(coords_latlon)

        folium.PolyLine(
            coords_latlon,
            color="blue",
            weight=2.5,
            opacity=0.9,
            tooltip=folium.Tooltip(f"Raw area: {area}", sticky=True),
        ).add_to(m)

    # Draw partitioned outputs (red)
    for area, segs in geopoints_map.items():
        for idx, way in enumerate(segs):
            path_latlon = [(lat, lon) for lon, lat in way]
            all_latlons.extend(path_latlon)

            folium.PolyLine(
                path_latlon,
                color="red",
                weight=2.5,
                opacity=0.95,
                tooltip=folium.Tooltip(f"{area} · segment {idx}", sticky=True),
            ).add_to(m)

            # Clickable/hoverable points
            for lat, lon in path_latlon:
                folium.CircleMarker(
                    location=(lat, lon),
                    radius=3,
                    color="red",
                    fill=True,
                    fill_opacity=1.0,
                    tooltip=folium.Tooltip(f"({lat:.6f}, {lon:.6f})", sticky=True),
                ).add_to(m)

    if all_latlons:
        min_lat = min(lat for lat, _ in all_latlons)
        max_lat = max(lat for lat, _ in all_latlons)
        min_lon = min(lon for _, lon in all_latlons)
        max_lon = max(lon for _, lon in all_latlons)

        center_lat = (min_lat + max_lat) / 2.0
        center_lon = (min_lon + max_lon) / 2.0

        m.location = (center_lat, center_lon)
        m.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])
    else:
        m.location = (0.0, 0.0)
        m.zoom_start = 4

    m.save(out_file)
    logger.info("Map saved to %s", out_file)
