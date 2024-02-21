# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import folium
import streamlit as st
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh
from folium.plugins import MiniMap
from util import stream_to_dataframe, connect_redis, get_drones, menu

if "location" not in st.session_state:
    st.session_state["location"] = [40.44482669, -79.90575779]
if "map_server" not in st.session_state:
    st.session_state.map_server = "Google Hybrid"
if "center" not in st.session_state:
    st.session_state.center = [40.415428612484924, -79.95028831875038]
if "tracking_selection" not in st.session_state:
    st.session_state.tracking_selection = None

COLORS = [
    "red",
    "blue",
    "gray",
    "darkred",
    "lightred",
    "orange",
    "beige",
    "green",
    "darkgreen",
    "lightgreen",
    "darkblue",
    "lightblue",
    "purple",
    "darkpurple",
    "pink",
    "cadetblue",
    "lightgray",
    "black",
]

st.set_page_config(
    page_title="Commander",
    page_icon=":world_map:",
    layout="wide",
    menu_items={
        'Get help': 'https://cmusatyalab.github.io/steeleagle/',
        'Report a bug': "https://github.com/cmusatyalab/steeleagle/issues",
        'About': "SteelEagle - Automated drone flights for visual inspection tasks\n https://github.com/cmusatyalab/steeleagle"
    }
)


def change_center():
    if st.session_state.tracking_selection is not None:
        df = stream_to_dataframe(
            red.xrevrange(
                f"telemetry.{st.session_state.tracking_selection}", "+", "-", 1
            )
        )
        for index, row in df.iterrows():
            st.session_state.center = [row["latitude"], row["longitude"]]


def draw_map():
    m = folium.Map(
        location=[40.415428612484924, -79.95028831875038],
        zoom_start=18,
        tiles=tiles,
    )

    MiniMap(toggle_display=True, tile_layer=tiles).add_to(m)
    fg = folium.FeatureGroup(name="Drone Markers")
    tracks = folium.FeatureGroup(name="Historical Tracks")
    # Draw(export=True).add_to(m)
    lc = folium.LayerControl()

    marker_color = 0
    for k in red.keys("telemetry.*"):
        df = stream_to_dataframe(red.xrevrange(f"{k}", "+", "-", 500))
        i = 0
        coords = []
        for index, row in df.iterrows():
            if i % 10 == 0:
                coords.append([row["latitude"], row["longitude"]])
            if i == 0:
                text = folium.DivIcon(
                    icon_size=(1, 1),
                    icon_anchor=(25, 0),
                    html=f'<div style="color:black;font-size: 12pt;font-weight: bold">{k.split(".")[-1]}</div>',
                )
                plane = folium.Icon(
                    icon="plane",
                    color=COLORS[marker_color],
                    prefix="glyphicon",
                    angle=int(row["bearing"]),
                )
                html = f'<img src="http://{st.secrets.webserver}/raw/{k.split(".")[-1]}/latest.jpg" height="250px" width="250px"/>'

                fg.add_child(
                    folium.Marker(
                        location=[
                            row["latitude"],
                            row["longitude"],
                        ],
                        # tooltip=k.split(".")[-1],
                        tooltip=html,
                        icon=plane,
                    )
                )

                fg.add_child(
                    folium.Marker(
                        location=[
                            row["latitude"],
                            row["longitude"],
                        ],
                        icon=text,
                    )
                )

            i += 1

        ls = folium.PolyLine(locations=coords, color=COLORS[marker_color])
        ls.add_to(tracks)
        marker_color += 1

    st_folium(
        m,
        key="overview_map",
        use_container_width=True,
        feature_group_to_add=[fg, tracks],
        layer_control=lc,
        returned_objects=[],
        center=st.session_state.center,
    )

menu()
red = connect_redis()

tiles_col = st.columns(5)
tiles_col[0].selectbox(
    key="map_server",
    label=":world_map: :blue[Tile Server]",
    options=("Google Sat", "Google Hybrid"),
)

st.session_state.tracking_selection = tiles_col[1].selectbox(
    key="drone_track",
    label=":dart: :red[Track Drone]",
    options=get_drones(),
    on_change=change_center(),
    index=None,
    placeholder="Select a drone to track...",
)

if st.session_state.map_server == "Google Sat":
    tileset = "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga"
elif st.session_state.map_server == "Google Hybrid":
    tileset = "https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}&s=Ga"

tiles = folium.TileLayer(
    name=st.session_state.map_server, tiles=tileset, attr="Google", max_zoom=20
)
draw_map()
refresh_count = st_autorefresh(interval=500, key="overview_refresh")
