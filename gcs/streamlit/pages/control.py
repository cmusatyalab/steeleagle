# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only
import time
import uuid
from zipfile import ZipFile

import folium
import streamlit as st
from folium.plugins import MiniMap
from st_keypressed import st_keypressed
from streamlit_folium import st_folium
from util import (
    COLORS,
    authenticated,
    connect_redis,
    connect_zmq,
    get_drones,
    menu,
    stream_to_dataframe,
)

import protocol.common_pb2 as common
import protocol.controlplane_pb2 as controlplane

if "map_server" not in st.session_state:
    st.session_state.map_server = "Google Hybrid"
if "center" not in st.session_state:
    st.session_state.center = {"lat": 40.413552, "lng": -79.949152}
if "tracking_selection" not in st.session_state:
    st.session_state.tracking_selection = None
if "selected_drones" not in st.session_state:
    st.session_state.selected_drones = []
if "script_file" not in st.session_state:
    st.session_state.script_file = None
if "inactivity_time" not in st.session_state:
    st.session_state.inactivity_time = 1  # min
if "trail_length" not in st.session_state:
    st.session_state.trail_length = 100
if "armed" not in st.session_state:
    st.session_state.armed = False
if "roll_speed" not in st.session_state:
    st.session_state.roll_speed = 1.0
if "yaw_speed" not in st.session_state:
    st.session_state.yaw_speed = 45
if "thrust_speed" not in st.session_state:
    st.session_state.thrust_speed = 1.0
if "pitch_speed" not in st.session_state:
    st.session_state.pitch_speed = 1.0
if "gimbal_rel" not in st.session_state:
    st.session_state.gimbal_rel = 15
if "gimbal_abs" not in st.session_state:
    st.session_state.gimbal_abs = 45
if "gimbal_relative_mode" not in st.session_state:
    st.session_state.gimbal_relative_mode = True
if "imagery_framerate" not in st.session_state:
    st.session_state.imagery_framerate = 2
if "show_drone_markers" not in st.session_state:
    st.session_state.show_drone_markers = True
if "show_gps_tracks" not in st.session_state:
    st.session_state.show_gps_tracks = True
if "show_slam_track" not in st.session_state:
    st.session_state.show_slam_track = False
if "show_landing_spot" not in st.session_state:
    st.session_state.show_landing_spot = False
if "zoom_level" not in st.session_state:
    st.session_state.zoom_level = 18
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

if "zmq" not in st.session_state:
    st.session_state.zmq = connect_zmq()

if not authenticated():
    st.stop()  # Do not continue if not authenticated

red = connect_redis()


def change_center():
    if st.session_state.tracking_selection is not None:
        df = stream_to_dataframe(
            red.xrevrange(
                f"telemetry:{st.session_state.tracking_selection}", "+", "-", 1
            )
        )
        for index, row in df.iterrows():
            st.session_state.center = {"lat": row["latitude"], "lng": row["longitude"]}


def run_flightscript():
    if len(st.session_state.script_file) == 0:
        st.toast("You haven't uploaded a script yet!", icon="🚨")
    else:
        filename = f"{time.time_ns()}.ms"
        path = f"{st.secrets.scripts_path}/{filename}"
        with ZipFile(path, "w") as z:
            for file in st.session_state.script_file:
                z.writestr(file.name, file.read())

        req = controlplane.Request()
        req.seq_num = int(time.time())
        req.timestamp.GetCurrentTime()
        for d in st.session_state.selected_drones:
            req.msn.drone_ids.append(d)
        req.msn.uuid = str(uuid.uuid4())
        req.msn.url = f"http://{st.secrets.webserver}/scripts/{filename}"
        req.msn.action = controlplane.MissionAction.DOWNLOAD
        st.session_state.zmq.send(req.SerializeToString())
        rep = st.session_state.zmq.recv()
        st.toast(
            f"Instructed {req.msn.drone_ids} to fly autonomous script.",
            icon="\u2601",
        )


def enable_manual():
    req = controlplane.Request()
    req.seq_num = int(time.time())
    req.timestamp.GetCurrentTime()
    for d in st.session_state.selected_drones:
        req.msn.drone_ids.append(d)
    req.msn.action = controlplane.MissionAction.STOP
    st.session_state.zmq.send(req.SerializeToString())
    rep = st.session_state.zmq.recv()
    st.toast(f"Telling drone {req.veh.drone_ids} to halt! Kill signal sent.")


def rth():
    req = controlplane.Request()
    req.seq_num = int(time.time())
    req.timestamp.GetCurrentTime()
    for d in st.session_state.selected_drones:
        req.veh.drone_ids.append(d)
    req.veh.action = controlplane.VehicleAction.RTH
    st.session_state.zmq.send(req.SerializeToString())
    rep = st.session_state.zmq.recv()
    st.toast(f"Instructed {req.veh.drone_ids} to return to home!")


@st.fragment(run_every=f"{1 / st.session_state.imagery_framerate}s")
def update_imagery():
    drone_list = []
    for k in red.keys("drone:*"):
        last_seen = float(red.hget(k, "last_seen"))
        if (
            time.time() - last_seen < st.session_state.inactivity_time * 60
        ):  # minutes -> seconds
            drone_name = k.split(":")[-1]
            drone_list.append(drone_name)

    st.selectbox(
        key="imagery_key",
        label=" **:blue-background[:material/photo_library: Imagery]**",
        options=drone_list,
        index=0,
    )
    st.image(
        f"http://{st.secrets.webserver}/raw/{st.session_state.imagery_key}/latest.jpg?a={time.time()}",
        use_container_width=True,
    )
    col1, col2, col3 = st.columns(3, vertical_alignment="top", border=True)
    with col1:
        st.caption("**:sleuth_or_spy: Object Detection**")
        st.image(
            f"http://{st.secrets.webserver}/detected/drones/{st.session_state.imagery_key}/latest.jpg?a={time.time()}"
        )
    with col2:
        st.caption("**:checkered_flag: Obstacle Avoidance**")
        st.image(f"http://{st.secrets.webserver}/moa/latest.jpg?a={time.time()}")
    with col3:
        st.caption("**:traffic_light: HSV Filtering**")
        st.image(
            f"http://{st.secrets.webserver}/detected/drones/{st.session_state.imagery_key}/hsv.jpg?a={time.time()}"
        )


@st.fragment(run_every="1s")
def draw_map():
    m = folium.Map(
        location=[st.session_state.center["lat"], st.session_state.center["lng"]],
        zoom_start=st.session_state.zoom_level,
        tiles=tiles,
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.checkbox(
        label="Drone Markers",
        key="show_drone_markers",
        value=st.session_state.show_drone_markers,
    )
    col2.checkbox(
        label="Historical Tracks",
        key="show_gps_tracks",
        value=st.session_state.show_gps_tracks,
    )
    col3.checkbox(
        label="SLAM Track",
        key="show_slam_track",
        value=st.session_state.show_slam_track,
    )
    col4.checkbox(
        label="Landing Spot",
        key="show_landing_spot",
        value=st.session_state.show_landing_spot,
    )

    MiniMap(toggle_display=True, tile_layer=tiles).add_to(m)
    fg = folium.FeatureGroup(name="Drone Markers")
    tracks = folium.FeatureGroup(name="Historical Tracks")
    slam_track = folium.FeatureGroup(name="SLAM Track")
    landing_spot = folium.FeatureGroup(name="Landing Spot")
    # Draw(export=True).add_to(m)
    lc = folium.LayerControl()

    marker_color = 0
    drone_list = []
    for k in red.keys("drone:*"):
        last_seen = float(red.hget(k, "last_seen"))
        if (
            time.time() - last_seen < st.session_state.inactivity_time * 60
        ):  # minutes -> seconds
            drone_name = k.split(":")[-1]
            drone_list.append(drone_name)
    for d in drone_list:
        df = stream_to_dataframe(
            red.xrevrange(f"telemetry:{d}", "+", "-", st.session_state.trail_length)
        )
        coords = []
        i = 0
        current_task = red.hget(f"drone:{d}", "current_task")
        if current_task == "":
            current_task = "idle"
        for index, row in df.iterrows():
            if i % 10 == 0:
                coords.append([row["latitude"], row["longitude"]])
            if st.session_state.show_drone_markers and i == 0:
                text = folium.DivIcon(
                    icon_size="null",  # set the size to null so that it expands to the length of the string inside in the div
                    icon_anchor=(-20, 30),
                    html=f'<div style="color:white;font-size: 12pt;font-weight: bold;background-color:{COLORS[marker_color]};">{d} [{row["rel_altitude"]:.2f}m]<br/>{current_task}</div>',
                )
                plane = folium.Icon(
                    icon="plane",
                    color=COLORS[marker_color],
                    prefix="glyphicon",
                    angle=int(row["bearing"]) % 360,
                )

                fg.add_child(
                    folium.Marker(
                        location=[
                            row["latitude"],
                            row["longitude"],
                        ],
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

        if st.session_state.show_gps_tracks:
            ls = folium.PolyLine(locations=coords, color=COLORS[marker_color])
            ls.add_to(tracks)
            marker_color += 1

    if st.session_state.show_slam_track:
        TYPES = {
            "pose_x": "float",
            "pose_y": "float",
            "pose_z": "float",
            "lat": "float",
            "lon": "float",
            "alt": "float",
        }

        ret = red.xrevrange("slam", "+", "-", st.session_state.trail_length)
        if len(ret) > 0:
            df = stream_to_dataframe(ret, types=TYPES)
            slam_coords = []
            i = 0
            for index, row in df.iterrows():
                slam_coords.append([row["lat"], row["lon"]])
                if i == 0:
                    text = folium.DivIcon(
                        icon_size="null",  # set the size to null so that it expands to the length of the string inside in the div
                        icon_anchor=(-20, 30),
                        html=f'<div style="color:white;font-size: 12pt;font-weight: bold;background-color:#c0c125;">{row["alt"]:.2f}m MSL</div>',
                    )
                    plane = folium.Icon(
                        icon="plane",
                        color="beige",
                        prefix="glyphicon",
                        # angle=int(row["bearing"]),
                    )

                    slam_track.add_child(
                        folium.Marker(
                            location=[
                                row["lat"],
                                row["lon"],
                            ],
                            icon=plane,
                        )
                    )

                    slam_track.add_child(
                        folium.Marker(
                            location=[
                                row["lat"],
                                row["lon"],
                            ],
                            icon=text,
                        )
                    )
                i += 1
            ls = folium.PolyLine(locations=slam_coords, color="#c0c125")
            ls.add_to(slam_track)

    if st.session_state.show_landing_spot:
        TYPES = {
            "lat": "float",
            "lon": "float",
        }

        ret = red.xrevrange("landing_spot", "+", "-", 1)
        if len(ret) > 0:
            df = stream_to_dataframe(ret, types=TYPES)
            landing_coords = []
            for index, row in df.iterrows():
                landing_coords = [row["lat"], row["lon"]]

            circle = folium.Circle(
                location=landing_coords,
                radius=2,
                color="orange",
                weight=2,
                # fill_opacity=0.6,
                # opacity=1,
                # fill_color="orange",
                # fill=False,  # gets overridden by fill_color
            )

            circle.add_to(landing_spot)

    def update_map_props():
        st.session_state.center = st.session_state["overview_map"]["center"]
        st.session_state.zoom_level = st.session_state["overview_map"]["zoom"]

    output = st_folium(
        m,
        key="overview_map",
        use_container_width=True,
        feature_group_to_add=[fg, tracks, slam_track, landing_spot],
        # layer_control=lc,
        center=st.session_state.center,
        height=500,
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

    tiles_col[1].selectbox(
        key="tracking_selection",
        label=":dart: **:green[Track Drone]**",
        options=get_drones(),
        on_change=change_center(),
        placeholder="Select a drone to track...",
    )

    tiles_col[2].number_input(
        ":heartbeat: **:red[Active Threshold (min)]**",
        step=1,
        min_value=1,
        key="inactivity_time",
        max_value=600000,
    )

    if st.session_state.map_server == "Google Sat":
        tileset = "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga"
    elif st.session_state.map_server == "Google Hybrid":
        tileset = "https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}&s=Ga"

    tiles = folium.TileLayer(
        name=st.session_state.map_server, tiles=tileset, attr="Google", max_zoom=22
    )

    tiles_col[3].number_input(
        ":straight_ruler: **:gray[Trail Length]**",
        step=25,
        min_value=25,
        max_value=200,
        key="trail_length",
    )
    mode = (
        "**:green-background[:joystick: Manual Control Enabled (armed)]**"
        if st.session_state.armed
        else "**:red-background[:joystick: Manual Control Disabled (disarmed)]**"
    )
    tiles_col[4].number_input(
        key="imagery_framerate",
        label=":camera: **:orange[Imagery FPS]**",
        min_value=1,
        max_value=10,
        step=1,
        value=2,
        format="%0d",
    )

col1, col2 = st.columns([0.6, 0.4])
with col1:
    update_imagery()

with col2:
    st.caption("**:blue-background[:globe_with_meridians: Flight Tracking]**")
    draw_map()

with st.sidebar:
    drone_list = get_drones()
    if len(drone_list) > 0:
        st.pills(
            label=":helicopter: **:orange[Swarm Control]** :helicopter:",
            options=drone_list.keys(),
            default=drone_list.keys(),
            format_func=lambda option: drone_list[option],
            selection_mode="multi",
            key="selected_drones",
        )

    else:
        st.caption("No active drones.")
    st.toggle(
        key="armed", label=":safety_vest: Arm Swarm?", value=st.session_state.armed
    )
    st.caption(mode)

    st.session_state.script_file = st.file_uploader(
        key="flight_uploader",
        label="**:violet[Upload Autonomous Mission Script]**",
        help="Upload a flight script.",
        type=["kml", "dsl"],
        label_visibility="visible",
        accept_multiple_files=True,
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

    if st.session_state.armed and len(st.session_state.selected_drones) > 0:
        c1, c2 = st.columns(spec=2, gap="small")
        c1.number_input(
            key="pitch_speed",
            label="Pitch (m/s)",
            min_value=0.0,
            max_value=5.0,
            value=2.0,
            step=0.5,
            format="%f",
        )
        c2.number_input(
            key="thrust_speed",
            label="Thrust (m/s)",
            min_value=0.0,
            max_value=5.0,
            value=2.0,
            step=0.5,
            format="%f",
        )
        c3, c4 = st.columns(spec=2, gap="small")
        c3.number_input(
            key="yaw_speed",
            label="Yaw (deg/s)",
            min_value=0,
            max_value=180,
            step=15,
            value=45,
            format="%d",
        )
        c4.number_input(
            key="roll_speed",
            label="Roll (m/s)",
            min_value=0.0,
            max_value=5.0,
            value=2.0,
            step=0.5,
            format="%f",
        )
        c5, c6 = st.columns(spec=2, gap="small")
        mode = (
            "**Gimbal Relative**"
            if st.session_state.gimbal_relative_mode
            else "**Gimbal Absolute**"
        )
        on = c5.toggle(
            key="gimbal_relative_mode",
            label=mode,
            value=st.session_state.gimbal_relative_mode,
        )
        if on:
            c5.number_input(
                key="gimbal_rel",
                label="Gimbal Pitch (deg/s)",
                min_value=0,
                max_value=30,
                step=5,
                value=15,
                format="%d",
            )
        else:
            c5.slider(
                key="gimbal_abs",
                label="Gimbal Pitch (deg)",
                min_value=-90,
                max_value=90,
                step=15,
                value=45,
                format="%d",
            )

        key_pressed = st_keypressed()
        req = controlplane.Request()
        req.seq_num = int(time.time())
        req.timestamp.GetCurrentTime()
        for d in st.session_state.selected_drones:
            req.veh.drone_ids.append(d)

        # req.cmd.manual = True
        st.caption(f"keypressed={key_pressed}")
        if key_pressed == "t":
            req.veh.action = controlplane.VehicleAction.TAKEOFF
            st.info(f"Instructed {req.veh.drone_ids} to takeoff.")
        elif key_pressed == "g":
            req.veh.action = controlplane.VehicleAction.LAND
            st.info(f"Instructed {req.veh.drone_ids} to land.")
        else:
            pitch = roll = yaw = thrust = gimbal_pitch = 0
            if key_pressed == "w":
                pitch = 1 * st.session_state.pitch_speed
            elif key_pressed == "s":
                pitch = -1 * st.session_state.pitch_speed
            elif key_pressed == "d":
                roll = 1 * st.session_state.roll_speed
            elif key_pressed == "a":
                roll = -1 * st.session_state.roll_speed
            elif key_pressed == "i":
                thrust = 1 * st.session_state.thrust_speed
            elif key_pressed == "k":
                thrust = -1 * st.session_state.thrust_speed
            elif key_pressed == "l":
                yaw = 1 * st.session_state.yaw_speed
            elif key_pressed == "j":
                yaw = -1 * st.session_state.yaw_speed
            elif key_pressed == "r":
                gimbal_pitch = 1 * st.session_state.gimbal_rel
            elif key_pressed == "f":
                gimbal_pitch = -1 * st.session_state.gimbal_rel

            if gimbal_pitch != 0 and st.session_state.gimbal_relative_mode:
                req.veh.gimbal_pose.pitch = gimbal_pitch
                req.veh.gimbal_pose.control_mode = (
                    common.PoseControlMode.POSITION_RELATIVE
                )
            elif yaw == 0 and pitch == 0 and roll == 0 and thrust == 0:
                req.veh.action = controlplane.VehicleAction.HOVER
            else:
                req.veh.velocity_body.angular_vel = yaw
                req.veh.velocity_body.forward_vel = pitch
                req.veh.velocity_body.right_vel = roll
                req.veh.velocity_body.up_vel = thrust
            if not st.session_state.gimbal_relative_mode:
                req.veh.gimbal_pose.pitch = st.session_state.gimbal_abs
                req.veh.gimbal_pose.control_mode = (
                    common.PoseControlMode.POSITION_ABSOLUTE
                )
            st.caption(req)
        key_pressed = None
        st.session_state.zmq.send(req.SerializeToString())
        rep = st.session_state.zmq.recv()
