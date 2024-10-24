# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import os
import time
import json
from zipfile import ZipFile
from cnc_protocol import cnc_pb2
import folium
import streamlit as st
from streamlit_folium import st_folium
from folium.plugins import MiniMap
from util import stream_to_dataframe, connect_redis, connect_zmq, get_drones, menu, COLORS, authenticated

if "map_server" not in st.session_state:
    st.session_state.map_server = "Google Hybrid"
if "center" not in st.session_state:
    st.session_state.center = [40.413552, -79.949152]
if "tracking_selection" not in st.session_state:
    st.session_state.tracking_selection = None
if "selected_drones" not in st.session_state:
    st.session_state.selected_drones = None
if "script_file" not in st.session_state:
    st.session_state.script_file = None
if "inactivity_time" not in st.session_state:
    st.session_state.inactivity_time = 1 #min
if "trail_length" not in st.session_state:
    st.session_state.trail_length = 500

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

if "zmq" not in st.session_state:
    st.session_state.zmq = connect_zmq()

if not authenticated():
    st.stop()  # Do not continue if not authenticated

red = connect_redis()

def change_center():
    if st.session_state.tracking_selection is not None:
        df = stream_to_dataframe(
            red.xrevrange(
                f"telemetry.{st.session_state.tracking_selection}", "+", "-", 1
            )
        )
        for index, row in df.iterrows():
            st.session_state.center = [row["latitude"], row["longitude"]]


def run_flightscript():
    if len(st.session_state.script_file) == 0:
        st.toast("You haven't uploaded a script yet!", icon="🚨")
    else:
        filename = f"{time.time_ns()}.ms"
        path = f"{st.secrets.scripts_path}/{filename}"
        with ZipFile(path, 'w') as z:
            for file in st.session_state.script_file:
                z.writestr(file.name, file.read())

        req = cnc_pb2.Extras()
        req.cmd.script_url = f"http://{st.secrets.webserver}/scripts/{filename}"
        req.commander_id = os.uname()[1]
        req.cmd.for_drone_id = json.dumps([d for d in st.session_state.selected_drones])
        st.session_state.zmq.send(req.SerializeToString())
        rep = st.session_state.zmq.recv()
        st.toast(
            f"Instructed {req.cmd.for_drone_id} to fly autonomous script.",
            icon="\u2601",
        )

def enable_manual():
    req = cnc_pb2.Extras()
    req.cmd.halt = True
    req.commander_id = os.uname()[1]
    req.cmd.for_drone_id = json.dumps([d for d in st.session_state.selected_drones])
    st.session_state.zmq.send(req.SerializeToString())
    rep = st.session_state.zmq.recv()
    st.toast(
        f"Telling drone {req.cmd.for_drone_id} to halt! Kill signal sent."
    )

def rth():
    req = cnc_pb2.Extras()
    req.cmd.rth = True
    req.cmd.manual = False
    req.commander_id = os.uname()[1]
    req.cmd.for_drone_id = json.dumps([d for d in st.session_state.selected_drones])
    st.session_state.zmq.send(req.SerializeToString())
    rep = st.session_state.zmq.recv()
    st.toast(f"Instructed {req.cmd.for_drone_id} to return to home!")

@st.fragment(run_every="1s")
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
        df = stream_to_dataframe(red.xrevrange(f"{k}", "+", "-", st.session_state.trail_length))
        last_update = (int(df.index[0].split("-")[0])/1000)
        if time.time() - last_update <  st.session_state.inactivity_time * 60: # minutes -> seconds
            coords = []
            i = 0
            drone_name = k.split(".")[-1]
            for index, row in df.iterrows():
                if i % 10 == 0:
                    coords.append([row["latitude"], row["longitude"]])
                if i == 0:
                    text = folium.DivIcon(
                        icon_size="null", #set the size to null so that it expands to the length of the string inside in the div
                        icon_anchor=(-20, 30),
                        html=f'<div style="color:white;font-size: 12pt;font-weight: bold;background-color:{COLORS[marker_color]};">{drone_name}&nbsp;({int(row["battery"])}%)</div>',

                    )
                    plane = folium.Icon(
                        icon="plane",
                        color=COLORS[marker_color],
                        prefix="glyphicon",
                        angle=int(row["bearing"]),
                    )
                    html = f'<img src="http://{st.secrets.webserver}/raw/{drone_name}/latest.jpg" height="250px" width="250px"/>'

                    fg.add_child(
                        folium.Marker(
                            location=[
                                row["latitude"],
                                row["longitude"],
                            ],
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
                            tooltip=html,
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

map_options = ("Google Sat", "Google Hybrid")
tiles_col = st.columns(5)
st.session_state.map_server = tiles_col[0].selectbox(
   # key="map_server",
    label=":world_map: **:blue[Tile Server]**",
    options=map_options,
    index=map_options.index(st.session_state.map_server)
)

st.session_state.tracking_selection = tiles_col[1].selectbox(
    key="drone_track",
    label=":dart: **:green[Track Drone]**",
    options=get_drones(),
    on_change=change_center(),
    index=get_drones().index(st.session_state.tracking_selection) if st.session_state.tracking_selection else None,
    placeholder="Select a drone to track...",
)

st.session_state.inactivity_time = tiles_col[2].number_input(":heartbeat: **:red[Active Threshold (min)]**", step=1, min_value=1, value=st.session_state.inactivity_time, max_value=600000)

if st.session_state.map_server == "Google Sat":
    tileset = "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga"
elif st.session_state.map_server == "Google Hybrid":
    tileset = "https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}&s=Ga"

tiles = folium.TileLayer(
    name=st.session_state.map_server, tiles=tileset, attr="Google", max_zoom=20
)

st.session_state.trail_length = tiles_col[3].number_input(":straight_ruler: **:gray[Trail Length]**", step=500, min_value=500, max_value=2500, value=st.session_state.trail_length)

col1, col2 = st.columns([3, 1])
with col1:
    draw_map()

with col2:
    st.session_state.selected_drones = st.multiselect(
        label=":helicopter: **:orange[Swarm Control]** :helicopter:",
        options=get_drones(),
        placeholder="Select one or more drones...",
        default=st.session_state.selected_drones
    )
    st.session_state.script_file = st.file_uploader(
        key="flight_uploader",
        label="**:violet[Upload Autonomous Mission Script]**",
        help="Upload a flight script.",
        type=["kml", "dsl"],
        label_visibility='visible',
        accept_multiple_files=True
    )
    st.button(
        key="autonomous_button",
        label=":world_map: Fly Script",
        type="primary",
        use_container_width=True,
        on_click=run_flightscript,
    )
    st.button(
        key="manual_button",
        label=":octagonal_sign: Halt All",
        help="Immediately tell drones to hover.",
        type="primary",
        disabled=False,
        use_container_width=True,
        on_click=enable_manual,
    )
    st.button(
        key="rth_button",
        label=":dart: Return Home",
        help="Return to last known home.",
        type="primary",
        use_container_width=True,
        on_click=rth,
    )

