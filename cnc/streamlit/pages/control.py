# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import asyncio
import json
import os
import time
from zipfile import ZipFile

import folium
import streamlit as st
from cnc_protocol import cnc_pb2
from folium.plugins import MiniMap
from st_keypressed import st_keypressed
from streamlit_folium import st_folium
from util import (
    COLORS,
    authenticated,
    connect_redis,
    connect_redis_publisher,
    connect_zmq,
    menu,
    stream_to_dataframe,
)

st.set_page_config(
    page_title="Commander",
    page_icon=":helicopter:",
    layout="wide",
    menu_items={
        'Get help': 'https://cmusatyalab.github.io/steeleagle/',
        'Report a bug': "https://github.com/cmusatyalab/steeleagle/issues",
        'About': "SteelEagle - Automated drone flights for visual inspection tasks\n https://github.com/cmusatyalab/steeleagle"
    }
)

if "armed" not in st.session_state:
    st.session_state.armed = False
if "manual_control" not in st.session_state:
    st.session_state.manual_control = True
if "autonomous" not in st.session_state:
    st.session_state.autonomous = False
if "rth_sent" not in st.session_state:
    st.session_state.rth_sent = False
if "script_file" not in st.session_state:
    st.session_state.script_file = None
if "key_pressed" not in st.session_state:
    st.session_state.key_pressed = ""
if "selected_drone" not in st.session_state:
    st.session_state.selected_drone = None
if "roll_speed" not in st.session_state:
    st.session_state.roll_speed = 50
if "yaw_speed" not in st.session_state:
    st.session_state.yaw_speed = 45
if "thrust_speed" not in st.session_state:
    st.session_state.thrust_speed = 50
if "pitch_speed" not in st.session_state:
    st.session_state.pitch_speed = 50
if "gimbal_speed" not in st.session_state:
    st.session_state.gimbal_speed = 50
if "subscriber" not in st.session_state:
    st.session_state.subscriber = connect_redis_publisher()
if "telemetry" not in st.session_state:
    st.session_state.telemetry = None
if "redis" not in st.session_state:
    st.session_state.redis = connect_redis()
if "zmq" not in st.session_state:
    st.session_state.zmq = connect_zmq()
if "imagery_framerate" not in st.session_state:
    st.session_state.imagery_framerate = 1


MAG_STATE = [
    "Calibrated",
    "Recommended",
    "Calib. Required!",
    "unused",
    "Perturbation!!",
]

if not authenticated():
    st.stop()  # Do not continue if not authenticated

async def update(live, avoidance, detection, hsv, status,):
    try:
        while True:
            live.image(f"http://{st.secrets.webserver}/raw/{st.session_state.selected_drone}/latest.jpg?a={time.time()}", use_column_width="auto")
            avoidance.image(f"http://{st.secrets.webserver}/moa/latest.jpg?a={time.time()}", use_column_width="auto")
            detection.image(f"http://{st.secrets.webserver}/detected/latest.jpg?a={time.time()}", use_column_width="auto")
            hsv.image(f"http://{st.secrets.webserver}/detected/hsv.jpg?a={time.time()}", use_column_width="auto")


            # message = st.session_state.subscriber.get_message()
            # if message is not None:
            #     image_np = np.frombuffer(message['data'], dtype=np.uint8)
            #     img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
            #     img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            #     live.image(img)

            columns = {
                "latitude": "Latitude",
                "longitude": "Longitude",
                "altitude": st.column_config.NumberColumn(
                    "Altitude",
                    format="%0.2f m",
                ),
                "rssi": st.column_config.NumberColumn(
                    "RSSI",
                    format="%d",
                ),
                "battery": st.column_config.ProgressColumn(
                    "Battery",
                    help="Battery  Percentage",
                    format="%d%%",
                    min_value=0,
                    max_value=100,
                ),
                "mag":  st.column_config.CheckboxColumn(label="Mag", width="small"),
                "bearing": st.column_config.NumberColumn(
                    "Heading",
                    format="%d°",
                  ),
            }

            order = ("altitude", "bearing", "battery", "mag", "rssi",)

            st.session_state.telemetry = stream_to_dataframe(st.session_state.redis.xrevrange(f"telemetry.{st.session_state.selected_drone}", "+", "-", 1))
            st.session_state.telemetry["latitude"] = st.session_state.telemetry["latitude"].clip(-90, 90)
            st.session_state.telemetry["longitude"] = st.session_state.telemetry["longitude"].clip(-180, 180)
            st.session_state.telemetry["mag"] = st.session_state.telemetry["mag"].transform(lambda x: x == 0)
            status.dataframe(st.session_state.telemetry, hide_index=False, use_container_width=True, column_order=order, column_config=columns)
            #map_container.map(data=st.session_state.telemetry, use_container_width=True, zoom=16, size=1)

            await asyncio.sleep(1/st.session_state.imagery_framerate)

    except asyncio.CancelledError:
        st.write("Update coroutine canceled.")

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
        req.cmd.for_drone_id = json.dumps([st.session_state.selected_drone])
        st.session_state.zmq.send(req.SerializeToString())
        rep = st.session_state.zmq.recv()
        st.toast(
            f"Instructed {req.cmd.for_drone_id} to fly autonomous script.",
            icon="\u2601",
        )

def enable_manual():
    st.session_state.rth_sent = False
    st.session_state.autonomous = False
    st.session_state.manual_control = True
    req = cnc_pb2.Extras()
    req.cmd.halt = True
    req.commander_id = os.uname()[1]
    req.cmd.for_drone_id = json.dumps([st.session_state.selected_drone])
    st.session_state.zmq.send(req.SerializeToString())
    rep = st.session_state.zmq.recv()
    st.toast(
        f"Assuming manual control of {st.session_state.selected_drone}! Kill signal sent."
    )

def rth():
    st.session_state.manual_control = False
    st.session_state.autonomous = False
    st.session_state.rth_sent = True
    req = cnc_pb2.Extras()
    req.cmd.rth = True
    req.cmd.manual = False
    req.commander_id = os.uname()[1]
    req.cmd.for_drone_id = json.dumps([st.session_state.selected_drone])
    st.session_state.zmq.send(req.SerializeToString())
    rep = st.session_state.zmq.recv()
    st.toast(f"Instructed {st.session_state.selected_drone} to return to home!")

@st.fragment(run_every="1s")
def draw_map():
    tileset = "https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}&s=Ga"
    tiles = folium.TileLayer(
        name="map_tileserver", tiles=tileset, attr="Google", max_zoom=20
    )

    m = folium.Map(
        location=[40.415428612484924, -79.95028831875038],
        zoom_start=18,
        tiles=tiles,
    )

    MiniMap(toggle_display=True, tile_layer=tiles).add_to(m)
    fg = folium.FeatureGroup(name="Current Location")

    marker_color = 0
    df = stream_to_dataframe(st.session_state.redis .xrevrange(f"telemetry.{st.session_state.selected_drone}", "+", "-", 1))
    last_update = (int(df.index[0].split("-")[0])/1000)
    i = 0
    for index, row in df.iterrows():
        text = folium.DivIcon(
            icon_size="null",  #set the size to null so that it expands to the length of the string inside in the div
            icon_anchor=(-20, 30),
            html=f'<div style="color:white;font-size: 12pt;font-weight: bold;background-color:{COLORS[marker_color]};">{st.session_state.selected_drone}</div>',
        )
        plane = folium.Icon(
            icon="plane",
            color=COLORS[marker_color],
            prefix="glyphicon",
            angle=int(row["bearing"]),
        )
        html = f'<img src="http://{st.secrets.webserver}/raw/{st.session_state.selected_drone}/latest.jpg" height="250px" width="250px"/>'
        st.session_state.center =[row['latitude'], row['longitude']]
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

    st_folium(
        m,
        key="overview_map",
        use_container_width=True,
        feature_group_to_add=fg,
        returned_objects=[],
        center=st.session_state.center,
        height=500
    )

menu(with_control=False)

with st.sidebar:
    # st.session_state.selected_drone = st.selectbox(
    #     label=":helicopter: :green[Available Drones]",
    #     options=get_drones(),
    #     placeholder="No drone selected...",

    #     index = get_drones().index(st.session_state.selected_drone)
    # )
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
        disabled=st.session_state.autonomous,
        use_container_width=True,
        on_click=run_flightscript,
    )
   # st.divider()
    st.button(
        key="manual_button",
        label=":joystick: Manual Control",
        help="Immediately take manual control of drone.",
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
        disabled=st.session_state.rth_sent,
        on_click=rth,
    )
    if st.session_state.manual_control:
        #st.subheader(f":blue[Manual Control Enabled]")
        mode = ":green[Manual (armed)]" if st.session_state.armed else ":red[Manual (disarmed)]"
        st.checkbox(key="armed", label="Arm Drone?")
        c1, c2 = st.columns(spec=2, gap="small")
        c1.number_input(key="pitch_speed", label="Pitch %", min_value=0, max_value=100, value=50, step=5, format="%d")
        c2.number_input(key = "thrust_speed", label="Thrust %", min_value=0, max_value=100, step=5, value=50, format="%d")
        c3, c4 = st.columns(spec=2, gap="small")
        c3.number_input(key = "yaw_speed", label="Yaw %", min_value=0, max_value=100, step=5, value=50, format="%d")
        c4.number_input(key = "roll_speed", label="Roll %", min_value=0, max_value=100, step=5, value=50, format="%d")
        c5, c6 = st.columns(spec=2, gap="small")
        c5.number_input(key = "gimbal_speed", label="Gimbal Pitch %", min_value=0, max_value=100, step=5, value=50, format="%d")
        c6.number_input(key = "imagery_framerate", label="Imagery Framerate", min_value=1, max_value=30, step=1, value=2, format="%0d")

    elif st.session_state.rth_sent:
        mode = ":orange[Return to Home Initiated]"
    elif st.session_state.script_file is not None:
        mode = ":violet[Autonomous Mode Enabled]"

status_container, imagery_container = st.columns(spec=[2, 3], gap="large")

with status_container:
    draw_map()
    #st.session_state.subscriber.punsubscribe()
    #st.session_state.subscriber.psubscribe(f'imagery.{st.session_state.selected_drone}')
    
    st.subheader(f":blue[{st.session_state.selected_drone}] Status - {mode}"
                    if st.session_state.selected_drone is not None else ":red[No Drone Connected]",
                    divider="gray",
                )
    status_container = st.empty()

with imagery_container:
    livefeed_container = st.empty()
    c1, c2, c3 = st.columns(spec=3, gap="small")
    with c1:
        avoidance = st.empty()
        st.markdown(":checkered_flag: **Obstacle Avoidance**")
    with c2:
        detection = st.empty()
        st.markdown(":sleuth_or_spy: **Object Detection**")
    with c3:
        hsv = st.empty()
        st.markdown(":traffic_light: **HSV Filtering**")

st.session_state.key_pressed = st_keypressed()
if st.session_state.armed and st.session_state.manual_control and st.session_state.selected_drone is not None:
    req = cnc_pb2.Extras()
    req.commander_id = os.uname()[1]
    req.cmd.for_drone_id = json.dumps([st.session_state.selected_drone])
    #req.cmd.manual = True
    if st.session_state.key_pressed == "t":
        req.cmd.takeoff = True
        st.info(f"Instructed {st.session_state.selected_drone} to takeoff.")
    elif st.session_state.key_pressed == "g":
        req.cmd.land = True
        st.info(f"Instructed {st.session_state.selected_drone} to land.")
    else:
        pitch = roll = yaw = thrust = gimbal_pitch = 0
        if st.session_state.key_pressed == "w":
            pitch = 1 * st.session_state.pitch_speed
        elif st.session_state.key_pressed == "s":
            pitch = -1 * st.session_state.pitch_speed
        elif st.session_state.key_pressed == "d":
            roll = 1 * st.session_state.roll_speed
        elif st.session_state.key_pressed == "a":
            roll = -1 * st.session_state.roll_speed
        elif st.session_state.key_pressed == "i":
            thrust = 1 * st.session_state.thrust_speed
        elif st.session_state.key_pressed == "k":
            thrust = -1 * st.session_state.thrust_speed
        elif st.session_state.key_pressed == "l":
            yaw = 1 * st.session_state.yaw_speed
        elif st.session_state.key_pressed == "j":
            yaw = -1 * st.session_state.yaw_speed
        elif st.session_state.key_pressed == "r":
            gimbal_pitch = 1 * st.session_state.gimbal_speed
        elif st.session_state.key_pressed == "f":
            gimbal_pitch = -1 * st.session_state.gimbal_speed
        #st.toast(f"PCMD(pitch = {pitch}, roll = {roll}, yaw = {yaw}, thrust = {thrust})")
        req.cmd.pcmd.yaw = yaw
        req.cmd.pcmd.pitch = pitch
        req.cmd.pcmd.roll = roll
        req.cmd.pcmd.gaz = thrust
        req.cmd.pcmd.gimbal_pitch = gimbal_pitch
    st.session_state.key_pressed = None
    st.session_state.zmq.send(req.SerializeToString())
    rep = st.session_state.zmq.recv()

asyncio.run(update(livefeed_container, avoidance, detection, hsv, status_container,))
