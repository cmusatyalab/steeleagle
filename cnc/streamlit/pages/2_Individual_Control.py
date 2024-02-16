# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
from st_keypressed import st_keypressed
import redis
import os
from cnc_protocol import cnc_pb2
import zmq
import time
import datetime
import pandas as pd
from streamlit_autorefresh import st_autorefresh
import json

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
if "map_server" not in st.session_state:
    st.session_state.map_server = "Google Hybrid"
if "center" not in st.session_state:
    st.session_state.center = [40.415428612484924, -79.95028831875038]
if "selected_drone" not in st.session_state:
    st.session_state.selected_drone = None
if "roll_speed" not in st.session_state:
    st.session_state.roll_speed = 25
if "yaw_speed" not in st.session_state:
    st.session_state.yaw_speed = 75
if "gaz_speed" not in st.session_state:
    st.session_state.gaz_speed = 75
if "pitch_speed" not in st.session_state:
    st.session_state.pitch_speed = 25

@st.cache_resource
def connect_redis():
    red = redis.Redis(host=st.secrets.redis, port=st.secrets.redis_port, username=st.secrets.redis_user, password=st.secrets.redis_pw,decode_responses=True)
    return red

@st.cache_resource
def connect_zmq():
    ctx = zmq.Context()
    z = ctx.socket(zmq.REQ)
    z.connect(f'tcp://{st.secrets.zmq}:{st.secrets.zmq_port}')
    return z

#Redis Connection
red = connect_redis()
#ZMQ Control Plane
z = connect_zmq()

MAG_STATE = [
    "Calibrated",
    "Recommended",
    "Calib. Required!",
    "unused",
    "Perturbation!!",
]

DATA_TYPES = {
    "latitude": 'float',
    "longitude": 'float',
    "altitude": 'float',
    "bearing": 'int',
    "rssi": 'int',
    "battery": 'int',
    "mag": 'int',
    #"sats": int,
}

def get_drones():
    l=[]
    for k in red.keys("telemetry.*"):
        l.append(k.split(".")[-1])
    return l

def get_telemetry(drone):
    results = red.xrevrange(f"telemetry.{drone}", "+", "-", 1)
    telemetry = results[0][1]
    telemetry["last_update"] = datetime.datetime.strftime(datetime.datetime.fromtimestamp(int(results[0][0].split("-")[0])/1000), "%d-%b-%Y %H:%M:%S") 
    return telemetry

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
    req = cnc_pb2.Extras()
    req.cmd.halt = True
    req.commander_id = os.uname()[1]
    req.cmd.for_drone_id = st.session_state.selected_drone
    z.send(req.SerializeToString())
    rep = z.recv()
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
    req.cmd.for_drone_id = st.session_state.selected_drone
    z.send(req.SerializeToString())
    rep = z.recv()
    st.toast(f"Instructed {st.session_state.selected_drone} to return to home!")

def stream_to_dataframe(results, types=DATA_TYPES ) -> pd.DataFrame:
    _container = {}
    for item in results:
        _container[item[0]] = json.loads(json.dumps(item[1]))

    df = pd.DataFrame.from_dict(_container, orient='index')
    if types is not None:
        df = df.astype(types)

    return df

def change_center():
    if st.session_state.selected_drone is not None:
        df = stream_to_dataframe(red.xrevrange(f"telemetry.{st.session_state.selected_drone}", "+", "-", 1))
        for index, row in df.iterrows():
            st.session_state.center =[row['latitude'], row['longitude']]

refresh_count = st_autorefresh(interval=500, key="individual_refresh")

c2, c3 = st.columns(spec=[2, 3], gap="large")


with st.sidebar:
    st.session_state.script_file = st.file_uploader(
        key="flight_uploader",
        label=" Fly Autonomous Mission",
        help="Upload a flight script.",
        type=["ms"],
        label_visibility='visible'
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
        #st.subheader(f":blue[Manual Control Enabled]")
        st.subheader(":red[Manual Speed Controls]", divider="gray")
        st.sidebar.slider(
            key="pitch_speed",
            label="Drone Pitch (forward/backward)",
            min_value=0,
            max_value=100,
            value=st.session_state.pitch_speed,
            step=5,
            format="%d%%"
        )
        st.sidebar.slider(
            key="gaz_speed",
            label="Drone Gaz (up/down)",
            min_value=0,
            max_value=100,
            value=st.session_state.gaz_speed,
            step=5,
            format="%d%%"
        )
        st.sidebar.slider(
            key="yaw_speed",
            label="Drone Yaw (turn left/right)",
            min_value=0,
            max_value=100,
            value=st.session_state.yaw_speed,
            step=5,
            format="%d%%"
        )
        st.sidebar.slider(
            key="roll_speed",
            label="Drone Roll (strafe left/right)",
            min_value=0,
            max_value=100,
            value=st.session_state.roll_speed,
            step=5,
            format="%d%%"
        )
    elif st.session_state.rth_sent:
        st.subheader(f":orange[Return to Home Initiated]")
    elif st.session_state.script_file is not None:
        st.subheader(f":violet[Autonomous Mode Enabled]")

with c2:
    tiles_col = st.columns(2)
    st.session_state.selected_drone = tiles_col[0].selectbox(
        key="drone_list",
        label=":helicopter: :green[Available Drones]",
        options=get_drones(),
        placeholder="No drone selected...",
        on_change=change_center(),
        index = None
    )
    tiles_col[1].selectbox(
        key="map_server",
        label=":world_map: :blue[Tile Server]",
        options=("Google Sat", "Google Hybrid"),
    )
    if st.session_state.map_server == "Google Sat":
        tileset = "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga"
    elif st.session_state.map_server == "Google Hybrid":
        tileset = "https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}&s=Ga"
    m = folium.Map(
        location=[40.415428612484924, -79.95028831875038],
        zoom_start=16,
        max_zoom=20,
        tiles=tileset,
        attr="Google",
    )
    fg = folium.FeatureGroup(name="markers")

    #Draw(export=True).add_to(m)
    if st.session_state.selected_drone is not None:
        telemetry = get_telemetry(st.session_state.selected_drone)
        plane = folium.Icon(
            icon="plane",
            color="red",
            prefix="glyphicon",
            angle=int(
                telemetry['bearing']
            ),
        )

        fg.add_child(
            folium.Marker(
                location=[
                    telemetry['latitude'],
                    telemetry['longitude'],
                ],
                tooltip=st.session_state.selected_drone,
                icon=plane,
            )
        )

    st_folium(
        key="individual_map",
        fig=m,
        use_container_width=True,
        height=400,
        feature_group_to_add=fg,
        returned_objects=[],
        center = st.session_state.center,
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
            value=f"{round(float(telemetry['altitude']), 2)} m",
            delta=f"{round(float(telemetry['altitude']) - st.session_state.prev_alt, 2)} m",
        )
        # status_cols[1].metric(
        #     label="Satellites",
        #     value=f"{int(telemetry['sats'])}",
        #     delta=f"{int(telemetry['sats']) - st.session_state.prev_sats}",
        # )
        status_cols[2].metric(
            label="RSSI",
            value=f"{int(telemetry['rssi'])}",
        )
        status_cols[3].metric(
            label="Battery",
            value=f"{int(telemetry['battery'])}%",
        )
        status_cols2 = st.columns(2)
        status_cols2[0].metric(
            label="Magnetometer",
            value=MAG_STATE[
                int(telemetry['mag'])
            ],
        )
        st.metric(
            label="Last Update",
            value=f"{telemetry['last_update']}",
        )
        # status_cols2[1].metric(
        #     label="Status",
        #     value=telemetry['status'],
        # )
        # st.session_state.prev_sats = int(
        #     st.session_state.list.loc[st.session_state.selected_drone].sats
        # )
        st.session_state.prev_alt = float(telemetry['altitude'])


with c3:
    tab1, tab2, tab3 = st.tabs(["Live", "Obstacle Avoidance", "Object Detection"])
    if st.session_state.selected_drone is not None:
        # message = st.session_state.subscriber.get_message(timeout=0.1)

        # if message and bytes(st.session_state.selected_drone, encoding='utf-8') == message['channel'].split(b'.')[-1]:
        #     image_np = np.fromstring(message['data'], dtype=np.uint8)
        #     img = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
        #     img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        #     tab1.image(img)
        #tab1.image(f"http://{st.secrets.webrtc}/api/frame.jpeg?src=file2&a={time.time()}", use_column_width="auto")
        #live = tab1.empty()
        #tab1.image(f"../server/steeleagle-vol/raw/{st.session_state.selected_drone}/latest.jpg")
        tab1.image(f"http://{st.secrets.webserver}/raw/{st.session_state.selected_drone}/latest.jpg?a={time.time()}")
    tab2.image(f"http://{st.secrets.webserver}/moa/latest.jpg?a={time.time()}", use_column_width="auto")
    tab3.image(
        f"http://{st.secrets.webserver}/detected/latest.jpg?a={time.time()}", use_column_width="auto"
    )

    #st.write(f":keyboard: {st.session_state.key_pressed}")
    st.session_state.key_pressed = st_keypressed()
    if st.session_state.manual_control and st.session_state.selected_drone is not None:
        req = cnc_pb2.Extras()
        req.commander_id = os.uname()[1]
        req.cmd.for_drone_id = st.session_state.selected_drone
        #req.cmd.manual = True
        if st.session_state.key_pressed == "t":
            req.cmd.takeoff = True
            st.info(f"Instructed {st.session_state.selected_drone} to takeoff.")
        elif st.session_state.key_pressed == "g":
            req.cmd.land = True
            st.info(f"Instructed {st.session_state.selected_drone} to land.")
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
            elif st.session_state.key_pressed == "i":
                gaz = 1 * st.session_state.gaz_speed
                st.write(gaz)
            elif st.session_state.key_pressed == "k":
                gaz = -1 * st.session_state.gaz_speed
            elif st.session_state.key_pressed == "l":
                yaw = 1 * st.session_state.yaw_speed
            elif st.session_state.key_pressed == "j":
                yaw = -1 * st.session_state.yaw_speed
            #st.toast(f"PCMD(pitch = {pitch}, roll = {roll}, yaw = {yaw}, gaz = {gaz})")
            req.cmd.pcmd.yaw = yaw
            req.cmd.pcmd.pitch = pitch
            req.cmd.pcmd.roll = roll
            req.cmd.pcmd.gaz = gaz
        z.send(req.SerializeToString())
        rep = z.recv()
