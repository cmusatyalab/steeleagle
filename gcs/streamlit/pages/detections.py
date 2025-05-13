# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only
import folium
import streamlit as st
from streamlit_folium import st_folium
from folium.plugins import MiniMap
from util import  connect_redis,  menu, COLORS, authenticated
import datetime
from pykml import parser
import json

if "map_server" not in st.session_state:
    st.session_state.map_server = "Google Hybrid"
if "center" not in st.session_state:
    st.session_state.center = {'lat':40.413552, 'lng':-79.949152}
if "zoom_level" not in st.session_state:
    st.session_state.zoom_level = 18
st.set_page_config(
    page_title="Commander",
    page_icon=":military_helmet:",
    layout="wide",
    menu_items={
        'Get help': 'https://cmusatyalab.github.io/steeleagle/',
        'Report a bug': "https://github.com/cmusatyalab/steeleagle/issues",
        'About': "SteelEagle - Automated drone flights for visual inspection tasks\n https://github.com/cmusatyalab/steeleagle"
    }
)


if not authenticated():
    st.stop()  # Do not continue if not authenticated

red = connect_redis()

@st.fragment(run_every="1s")
def draw_map():
    m = folium.Map(
        location=[st.session_state.center['lat'], st.session_state.center['lng']],
        zoom_start=st.session_state.zoom_level,
        tiles=tiles,
    )

    MiniMap(toggle_display=True, tile_layer=tiles).add_to(m)
    fg = folium.FeatureGroup(name="Detected Objects")
    fence_fg = folium.FeatureGroup(name="Geofence")
    partitions = folium.FeatureGroup(name="Partitions")
    # Draw(export=True).add_to(m)
    lc = folium.LayerControl()

    try:
        partition = []
        with open(f"{st.secrets.waypoints}", 'r', encoding='utf-8') as f:
            j = json.load(f)
            for k, v in j.items():
                for k2, v2 in v.items(): #for each corridor
                    for c in v2:
                        lon = c[0]
                        lat = c[1]
                        partition.append([float(lat), float(lon)])

        ls = folium.PolyLine(locations=partition, color="blue")
        ls.add_to(partitions)
    except OSError:
        st.toast(f"Error loading waypoint partitions from {st.secrets.waypoints}.")

    try:
        fence_coords = []
        with open(f"{st.secrets.geofence_path}", 'r', encoding='utf-8') as f:
            root = parser.parse(f).getroot()
            coords = root.Document.Placemark.Polygon.outerBoundaryIs.LinearRing.coordinates.text
            for c in coords.split():
                lon, lat, alt =  c.split(",")
                fence_coords.append([float(lat), float(lon)])

        ls = folium.PolyLine(locations=fence_coords, color="yellow")
        ls.add_to(fence_fg)
    except OSError:
        st.toast(f"Error loading geofence from {st.secrets.geofence_path}.")

    marker_color = 0
    for obj in red.zrange("detections", 0, -1):
        if len(red.keys(f"objects:{obj}")) > 0:
            fields = red.hgetall(f"objects:{obj}")
            img_ref = f'<img src="{fields["link"]}" height="360px" width="480px"/>'
            div_content = f"""
                    <div style="color:white;font-size: 12pt;font-weight: bold;background-color:{COLORS[marker_color]};">
                        {obj}&nbsp;({float(fields["confidence"]):.2f})&nbsp;[{fields["drone_id"]}]<br/>
                        {datetime.datetime.fromtimestamp(float(fields["last_seen"])).strftime('%Y-%m-%d %H:%M:%S')}
                    </div>
                """

            text = folium.DivIcon(
                icon_size="null", #set the size to null so that it expands to the length of the string inside in the div
                icon_anchor=(-20, 30),
                html=div_content,
            )
            object_icon = folium.Icon(
                icon="object-group",
                color=COLORS[marker_color],
                prefix="fa",
            )

            fg.add_child(
                folium.Marker(
                    location=[
                        fields["latitude"],
                        fields["longitude"],
                    ],
                    icon=object_icon,
                )
            )

            fg.add_child(
                folium.Marker(
                    location=[
                        fields["latitude"],
                        fields["longitude"],
                    ],
                    icon=text,
                    tooltip=img_ref
                )
            )

    def update_map_props():
        st.session_state.center = st.session_state['overview_map']['center']
        st.session_state.zoom_level = st.session_state['overview_map']['zoom']

    st_folium(
        m,
        key="overview_map",
        use_container_width=True,
        feature_group_to_add=[fg, fence_fg, partitions],
        layer_control=lc,
        center=st.session_state.center,
        height=720,
        on_change=update_map_props
    )

menu()
options_expander = st.expander(" **:gray-background[:wrench: Toolbar]**", expanded=True)

with options_expander:
    map_options = ["Google Sat", "Google Hybrid"]
    tiles_col = st.columns(5)
    tiles_col[0].selectbox(
        key="map_server",
        label=":world_map: **:blue[Tile Server]**",
        options=map_options,
        index=0
    )

if st.session_state.map_server == "Google Sat":
    tileset = "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga"
elif st.session_state.map_server == "Google Hybrid":
    tileset = "https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}&s=Ga"

tiles = folium.TileLayer(
    name=st.session_state.map_server, tiles=tileset, attr="Google", max_zoom=23
)

st.caption("**:blue-background[:globe_with_meridians: Detected Objects]**")
draw_map()

