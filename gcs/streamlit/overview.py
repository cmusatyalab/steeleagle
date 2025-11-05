# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only
import folium
import streamlit as st
from streamlit_folium import st_folium
from folium.plugins import MiniMap
from util import connect_redis, menu, authenticated, stream_to_dataframe
import datetime
from pykml import parser
import json
import time
from colorhash import ColorHash

if "map_server" not in st.session_state:
    st.session_state.map_server = "Google Hybrid"
if "center" not in st.session_state:
    st.session_state.center = {"lat": 40.413552, "lng": -79.949152}
if "zoom_level" not in st.session_state:
    st.session_state.zoom_level = 18
if "show_drone_markers" not in st.session_state:
    st.session_state.show_drone_markers = True
if "show_geofence" not in st.session_state:
    st.session_state.show_geofence = True
if "show_objects" not in st.session_state:
    st.session_state.show_objects = True
if "show_corridors" not in st.session_state:
    st.session_state.show_corridors = False

st.set_page_config(
    page_title="Commander",
    page_icon=":military_helmet:",
    layout="wide",
    menu_items={
        "Get help": "https://cmusatyalab.github.io/steeleagle/",
        "Report a bug": "https://github.com/cmusatyalab/steeleagle/issues",
        "About": "SteelEagle - Automated drone flights for visual inspection tasks\n https://github.com/cmusatyalab/steeleagle",
    },
)


if not authenticated():
    st.stop()  # Do not continue if not authenticated

red = connect_redis()


@st.fragment(run_every="1s")
def draw_map():
    m = folium.Map(
        location=[st.session_state.center["lat"], st.session_state.center["lng"]],
        zoom_start=st.session_state.zoom_level,
        tiles=tiles,
    )

    MiniMap(toggle_display=True, tile_layer=tiles).add_to(m)
    fg = folium.FeatureGroup(name="Detected Objects")
    fence_fg = folium.FeatureGroup(name="Geofence")
    partitions = folium.FeatureGroup(name="Partitions")
    drone_positions = folium.FeatureGroup(name="Drone Markers")
    # Draw(export=True).add_to(m)
    lc = folium.LayerControl()
    if st.session_state.show_drone_markers:
        for k in red.keys("telemetry:*"):
            df = stream_to_dataframe(red.xrevrange(f"{k}", "+", "-", 1))
            last_update = int(df.index[0].split("-")[0]) / 1000
            if time.time() - last_update < 60:
                coords = []
                i = 0
                drone_name = k.split(":")[-1]
                for index, row in df.iterrows():
                    if i == 0:
                        coords.append([row["latitude"], row["longitude"]])
                        text = folium.DivIcon(
                            icon_size="null",  # set the size to null so that it expands to the length of the string inside in the div
                            icon_anchor=(-20, 30),
                            html=f'<div style="color:white;font-size: 12pt;font-weight: bold;background-color:{ColorHash({drone_name}).hex};">{drone_name}</div>',
                            # TODO: concatenate current task to html once it is sent i.e. <i>PatrolTask</i></div>
                        )
                        plane = folium.Icon(
                            icon="plane",
                            color="lightgray",
                            icon_color=ColorHash({drone_name}).hex,
                            prefix="glyphicon",
                            angle=int(row["bearing"]),
                        )

                        drone_positions.add_child(
                            folium.Marker(
                                location=[
                                    row["latitude"],
                                    row["longitude"],
                                ],
                                icon=plane,
                            )
                        )

                        drone_positions.add_child(
                            folium.Marker(
                                location=[
                                    row["latitude"],
                                    row["longitude"],
                                ],
                                icon=text,
                            )
                        )

    if st.session_state.show_corridors:
        try:
            partition = []
            with open(f"{st.secrets.waypoints}", "r", encoding="utf-8") as f:
                j = json.load(f)
                for k, v in j.items():
                    for k2, v2 in v.items():  # for each corridor
                        for c in v2:
                            lon = c[0]
                            lat = c[1]
                            partition.append([float(lat), float(lon)])

            ls = folium.PolyLine(locations=partition, color="white", opacity=0.3)
            ls.add_to(partitions)
        except OSError:
            st.toast(f"Error loading waypoint partitions from {st.secrets.waypoints}.")
    if st.session_state.show_geofence:
        try:
            fence_coords = []
            with open(f"{st.secrets.geofence_path}", "r", encoding="utf-8") as f:
                root = parser.parse(f).getroot()
                coords = root.Document.Placemark.Polygon.outerBoundaryIs.LinearRing.coordinates.text
                for c in coords.split():
                    lon, lat, alt = c.split(",")
                    fence_coords.append([float(lat), float(lon)])

            ls = folium.PolyLine(locations=fence_coords, color="yellow")
            ls.add_to(fence_fg)
        except OSError:
            st.toast(f"Error loading geofence from {st.secrets.geofence_path}.")

    if st.session_state.show_objects:
        for obj in red.zrange("detections", 0, -1):
            if len(red.keys(f"objects:{obj}")) > 0:
                fields = red.hgetall(f"objects:{obj}")
                img_ref = f'<img src="{fields["link"]}" height="360px" width="480px"/>'
                div_content = f"""
                        <div style="color:white;font-size: 12pt;font-weight: bold;background-color:{ColorHash({obj}).hex};">
                            {obj}&nbsp;({float(fields["confidence"]):.2f})&nbsp;[{fields["drone_id"]}]<br/>
                            {datetime.datetime.fromtimestamp(float(fields["last_seen"])).strftime("%Y-%m-%d %H:%M:%S")}
                        </div>
                    """

                text = folium.DivIcon(
                    icon_size="null",  # set the size to null so that it expands to the length of the string inside in the div
                    icon_anchor=(-20, 30),
                    html=div_content,
                )
                object_icon = folium.Icon(
                    icon="object-group",
                    color=ColorHash({obj}).hex,
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
                        tooltip=img_ref,
                    )
                )

    def update_map_props():
        st.session_state.center = st.session_state["overview_map"]["center"]
        st.session_state.zoom_level = st.session_state["overview_map"]["zoom"]

    st_folium(
        m,
        key="overview_map",
        width="stretch",
        feature_group_to_add=[fg, fence_fg, partitions, drone_positions],
        layer_control=lc,
        center=st.session_state.center,
        height=720,
        on_change=update_map_props,
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
        index=0,
    )
    tiles_col[1].checkbox(
        label="Drone Markers",
        key="show_drone_markers",
        value=st.session_state.show_drone_markers,
    )
    tiles_col[2].checkbox(
        label="Detected Objects",
        key="show_objects",
        value=st.session_state.show_objects,
    )
    tiles_col[3].checkbox(
        label="Detections Geofence",
        key="show_geofence",
        value=st.session_state.show_geofence,
    )
    tiles_col[4].checkbox(
        label="Mission Corridors",
        key="show_corridors",
        value=st.session_state.show_corridors,
    )

if st.session_state.map_server == "Google Sat":
    tileset = "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga"
elif st.session_state.map_server == "Google Hybrid":
    tileset = "https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}&s=Ga"

tiles = folium.TileLayer(
    name=st.session_state.map_server, tiles=tileset, attr="Google", max_zoom=23
)

draw_map()
