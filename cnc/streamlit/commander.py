# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import streamlit as st
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
from st_keypressed import st_keypressed
import streamlit_antd_components as sac
import zmq

st.set_page_config(
    page_title="Commander",
    page_icon=":helicopter:",
    layout="wide",
)

if "selected_drone" not in st.session_state:
    st.session_state.selected_drone = None
if "manual_control" not in st.session_state:
    st.session_state.manual_control = True
if "autonomous" not in st.session_state:
    st.session_state.autonomous = False
if "rth_sent" not in st.session_state:
    st.session_state.rth_sent = False
if "script_file" not in st.session_state:
    st.session_state.script_file = None
if "prev_sats" not in st.session_state:
    st.session_state.prev_sats = 0
if "prev_alt" not in st.session_state:
    st.session_state.prev_alt = 0
if "key_pressed" not in st.session_state:
    st.session_state.key_pressed = ""
if "list" not in st.session_state:
    st.session_state.list = []
if "map_server" not in st.session_state:
    st.session_state.map_server = "Google Hybrid"
if "zmq_context" not in st.session_state:
    st.session_state.zmq_context = zmq.Context()
    st.session_state.publisher = st.session_state.zmq_context.socket(zmq.REQ)
    try:
        st.session_state.publisher.connect(f"tcp://localhost:5577")
    except zmq.ZMQError:
        st.error("ZMQ cannot connect to port 5577. Is the ZQM REP server up?")
        st.stop()

MAG_STATE = [
    "Calibrated",
    "Recommended",
    "Calib. Required!",
    "unused",
    "Perturbation!!",
]
DATA_TYPES = {
    "key": str,
    "latitude": float,
    "longitude": float,
    "altitude": float,
    "bearing": int,
    "rssi": int,
    "battery": int,
    "mag": int,
    "sats": int,
}


try:
    st.session_state.list = pd.read_csv(
        filepath_or_buffer="./dronelist.csv", index_col=0, dtype=DATA_TYPES
    )
except pd.errors.EmptyDataError:
    st.session_state.list = []


def run_flightscript():
    if st.session_state.script_file is None:
        st.toast("You haven't uploaded a script yet!", icon="🚨")
    else:
        bytes_data = st.session_state.script_file.getvalue()
        fd = open(file=st.session_state.script_file.name, mode="wb")
        fd.write(bytes_data)
        st.session_state.manual_control = False
        st.session_state.rth_sent = False
        st.session_state.autonomous = True
        # TODO: Copy ms to /var/www/html/scripts and then instruct drone to flight the script
        st.toast(
            f"Instructed {st.session_state.selected_drone} to fly autonomous script",
            icon="\u2601",
        )
        st.session_state.publisher.send_json(
            {
                "drone_id": st.session_state.selected_drone,
                "script": st.session_state.script_file.name,
            }
        )
        message = st.session_state.publisher.recv_string()


def enable_manual():
    st.session_state.rth_sent = False
    st.session_state.autonomous = False
    st.session_state.manual_control = True
    st.session_state.publisher.send_json(
        {"drone_id": st.session_state.selected_drone, "kill": True}
    )
    message = st.session_state.publisher.recv_string()
    st.toast(
        f"Assuming manual control of {st.session_state.selected_drone}! Kill signal sent."
    )


def rth():
    st.session_state.manual_control = False
    st.session_state.autonomous = False
    st.session_state.rth_sent = True
    st.session_state.publisher.send_json(
        {"drone_id": st.session_state.selected_drone, "rth": True}
    )
    message = st.session_state.publisher.recv_string()
    st.toast(f"Instructed {st.session_state.selected_drone} to return to home!")


refresh_count = st_autorefresh(interval=1000, key="refreshcounter")
c2, c3 = st.columns(spec=[2, 3], gap="large")

with st.sidebar:
    st.session_state.selected_drone = st.selectbox(
        key="drone_list",
        label=":blue[Available Drones]",
        options=st.session_state.list.index,
        placeholder="No drone selected...",
    )
    st.button(
        key="autonomous_button",
        label=":world_map: Fly Script",
        type="primary",
        disabled=st.session_state.autonomous,
        use_container_width=True,
        on_click=run_flightscript,
    )
    st.session_state.script_file = st.file_uploader(
        key="flight_uploader",
        label=" Fly Autonomous Mission",
        help="Upload a flight script.",
        type=["ms"],
    )
    st.divider()
    st.button(
        key="manual_button",
        label=":joystick: Manual Control",
        help="Immediately take manual control of drone.",
        type="primary",
        disabled=st.session_state.manual_control,
        use_container_width=True,
        on_click=enable_manual,
    )
    st.button(
        key="rth_button",
        label=":dart: Return Home",
        help="Return to last known home.",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.rth_sent,
        on_click=rth,
    )

    if st.session_state.manual_control:
        st.subheader(f":blue[Manual Control Enabled]")
    elif st.session_state.rth_sent:
        st.subheader(f":orange[Return to Home Initiated]")
    elif st.session_state.script_file is not None:
        st.subheader(f":violet[Autonomous Mode Enabled]")


with c2:
    tiles_col = st.columns(2)
    tiles_col[0].selectbox(
        key="map_server",
        label=":blue[Tile Server]",
        options=("Google Sat", "Google Hybrid"),
    )
    if st.session_state.map_server == "Google Sat":
        tileset = "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga"
    elif st.session_state.map_server == "Google Hybrid":
        tileset = "https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}&s=Ga"
    m = folium.Map(
        location=[40.415428612484924, -79.95028831875038],
        zoom_start=16,
        tiles=tileset,
        attr="Google",
    )
    fg = folium.FeatureGroup(name="markers")
    #Draw(export=True).add_to(m)
    if st.session_state.selected_drone is not None:
        plane = folium.Icon(
            icon="plane",
            color="red",
            prefix="glyphicon",
            angle=int(
                st.session_state.list.loc[st.session_state.selected_drone].bearing
            ),
        )

        fg.add_child(
            folium.Marker(
                location=[
                    st.session_state.list.loc[st.session_state.selected_drone].latitude,
                    st.session_state.list.loc[
                        st.session_state.selected_drone
                    ].longitude,
                ],
                tooltip=st.session_state.selected_drone,
                icon=plane,
            )
        )
    output = st_folium(
        key="bearing_map",
        fig=m,
        use_container_width=True,
        height=400,
        feature_group_to_add=fg,
    )

    st.subheader(
        f":blue[{st.session_state.selected_drone}] Status"
        if st.session_state.selected_drone is not None
        else ":red[No Drone Connected]",
        divider="gray",
    )
    if st.session_state.selected_drone is not None:
        status_cols = st.columns(4)
        status_cols[0].metric(
            label="Altitude",
            value=f"{st.session_state.list.loc[st.session_state.selected_drone].altitude} m",
            delta=f"{st.session_state.list.loc[st.session_state.selected_drone].altitude - st.session_state.prev_alt} m",
        )
        status_cols[1].metric(
            label="Satellites",
            value=f"{int(st.session_state.list.loc[st.session_state.selected_drone].sats)}",
            delta=f"{int(st.session_state.list.loc[st.session_state.selected_drone].sats) - st.session_state.prev_sats}",
        )
        status_cols[2].metric(
            label="RSSI",
            value=f"{int(st.session_state.list.loc[st.session_state.selected_drone].rssi)}",
        )
        status_cols[3].metric(
            label="Battery",
            value=f"{int(st.session_state.list.loc[st.session_state.selected_drone].battery)}%",
        )
        status_cols2 = st.columns(2)
        status_cols2[0].metric(
            label="Magnetometer",
            value=MAG_STATE[
                int(st.session_state.list.loc[st.session_state.selected_drone].mag)
            ],
        )
        status_cols2[1].metric(
            label="Status",
            value=st.session_state.list.loc[st.session_state.selected_drone].status,
        )
        st.session_state.prev_sats = int(
            st.session_state.list.loc[st.session_state.selected_drone].sats
        )
        st.session_state.prev_alt = st.session_state.list.loc[
            st.session_state.selected_drone
        ].altitude

with c3:
    tab1, tab2, tab3 = st.tabs(["Live", "Obstacle Avoidance", "Object Detection"])
    if st.session_state.selected_drone is not None:
        tab1.image(
            f"../server/openscout-vol/received/{st.session_state.selected_drone}/latest.jpg",
            use_column_width="auto",
        )
        tab2.image(f"../server/openscout-vol/moa/latest.jpg", use_column_width="auto")
        tab3.image(
            f"../server/openscout-vol/detected/latest.jpg", use_column_width="auto"
        )
    st.subheader(":red[Manual Speed Controls]", divider="gray")
    speed_cols1 = st.columns(2)
    speed_cols1[0].slider(
        key="pitch_speed",
        label="Drone Pitch (forward/backward)",
        min_value=0,
        max_value=100,
        value=10,
        step=5,
    )
    speed_cols1[1].slider(
        key="gaz_speed",
        label="Drone Gaz (up/down)",
        min_value=0,
        max_value=100,
        value=10,
        step=5,
    )
    speed_cols2 = st.columns(2)
    speed_cols2[0].slider(
        key="yaw_speed",
        label="Drone Yaw (turn left/right)",
        min_value=0,
        max_value=100,
        value=10,
        step=5,
    )
    speed_cols2[1].slider(
        key="roll_speed",
        label="Drone Roll (strafe left/right)",
        min_value=0,
        max_value=100,
        value=10,
        step=5,
    )

    st.write(f":keyboard: {st.session_state.key_pressed}")
    st.session_state.key_pressed = st_keypressed()
    if st.session_state.manual_control and st.session_state.selected_drone != None:
        if st.session_state.key_pressed == "t":
            st.session_state.publisher.send_json(
                {"drone_id": st.session_state.selected_drone, "takeoff": True}
            )
            message = st.session_state.publisher.recv_string()
            st.toast(f"Instructed {st.session_state.selected_drone} to takeoff.")
        elif st.session_state.key_pressed == "l":
            st.session_state.publisher.send_json(
                {"drone_id": st.session_state.selected_drone, "land": True}
            )
            message = st.session_state.publisher.recv_string()
            st.toast(f"Instructed {st.session_state.selected_drone} to land.")
        else:
            pitch = roll = yaw = gaz = 0
            if st.session_state.key_pressed == "w":
                pitch = 1 * st.session_state.pitch_speed
            elif st.session_state.key_pressed == "s":
                pitch = -1 * st.session_state.pitch_speed
            elif st.session_state.key_pressed == "d":
                roll = 1 * st.session_state.roll_speed
            elif st.session_state.key_pressed == "a":
                roll = -1 * st.session_state.roll_speed
            elif st.session_state.key_pressed == "ArrowUp":
                gaz = 1 * st.session_state.gaz_speed
            elif st.session_state.key_pressed == "ArrowDown":
                gaz = -1 * st.session_state.gaz_speed
            elif st.session_state.key_pressed == "ArrowRight":
                yaw = 1 * st.session_state.yaw_speed
            elif st.session_state.key_pressed == "ArrowLeft":
                yaw = -1 * st.session_state.yaw_speed
            st.session_state.publisher.send_json(
                {
                    "drone_id": st.session_state.selected_drone,
                    "pitch": pitch,
                    "roll": roll,
                    "yaw": yaw,
                    "gaz": gaz,
                }
            )
            message = st.session_state.publisher.recv_string()
            st.toast(f"PCMD(pitch = {pitch}, roll = {roll}, yaw = {yaw}, gaz = {gaz})")

# st.write(st.session_state)
