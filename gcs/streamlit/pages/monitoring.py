# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only
import time

import streamlit as st
from util import authenticated, connect_redis, connect_zmq, menu, stream_to_dataframe

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

if "zmq" not in st.session_state:
    st.session_state.zmq = connect_zmq()
if "inactivity_time" not in st.session_state:
    st.session_state.inactivity_time = 1 #min
if "refresh_rate" not in st.session_state:
    st.session_state.refresh_rate = 2 #sec

if not authenticated():
    st.stop()  # Do not continue if not authenticated

red = connect_redis()

@st.fragment(run_every=st.session_state.refresh_rate)
def plot_data():
   cols = st.columns(2)
   i = 0
   for k in red.keys("drone:*"):
        last_seen = float(red.hget(k, "last_seen"))
        if time.time() - last_seen <  st.session_state.inactivity_time * 60: # minutes -> seconds
            drone_name = k.split(":")[-1]
            drone_model = red.hget(k, "model")
            if drone_model == "":
                drone_model = "unknown"
            bat = int(red.hget(k, "battery"))
            if bat == 0:
               bat_status = ":green-badge[:material/battery_full: Nominal Battery]"
            elif bat == 1:
                bat_status = ":orange-badge[:material/battery_3_bar: Low Battery]"
            else:
                bat_status = ":red-badge[:material/battery_alert: Critical Battery]"

            mag = int(red.hget(k, "mag"))
            if mag == 0:
                mag_status = ":green-badge[:material/explore: No Interference]"
            elif mag == 1:
                mag_status = ":orange-badge[:material/explore: Magnetic Perturbation]"
            else:
                mag_status = ":red-badge[:material/explore: Strong Magnetic Interference]"

            sats = int(red.hget(k, "sats"))
            if sats == 0:
                sat_status = ":green-badge[:material/satellite_alt: Nominal GPS]"
            elif sats == 1:
                sat_status = ":orange-badge[:material/satellite_alt: Poor GPS Signal]"
            elif sats == 2:
                sat_status = ":red-badge[:material/satellite_alt: No GPS Signal]"

            slam = red.hget(k, "slam_registering")
            if slam:
                slam_status = ":green-badge[:material/globe_location_pin: SLAM Localized]"
            else:
                slam_status = ":red-badge[:material/globe_location_pin: SLAM Not Localized]"

            current_task = red.hget(k, "current_task")
            task_status = f":blue-badge[:material/format_list_numbered: {current_task}]"
            df = stream_to_dataframe(red.xrevrange(f"telemetry:{drone_name}", "+", "-", 1))
            column_config={
                    "_index": None,
                    "latitude": st.column_config.NumberColumn(
                        "Lat",
                        format="%.3f",
                    ),
                    "longitude": st.column_config.NumberColumn(
                        "Lon",
                        format="%.3f",
                    ),
                    "rel_altitude": st.column_config.NumberColumn(
                        "Alt (AGL)",
                        format="%.1f",
                    ),
                    "abs_altitude": st.column_config.NumberColumn(
                        "Alt (MSL)",
                        format="%.1f",
                    ),
                    "sats": st.column_config.NumberColumn(
                        "# Sats",
                        format="%d",
                    ),
                    "bearing": st.column_config.NumberColumn(
                        "Bearing",
                        format="%d",
                    ),
                    "battery": st.column_config.ProgressColumn(
                        "Battery",
                        format="%d",
                        min_value=0,
                        max_value=100,
                    ),
                    "mag": None,
                }
            cols[i%2].markdown(f"### **{drone_name} ({drone_model})**")
            cols[i%2].image(f"http://{st.secrets.webserver}/raw/{drone_name}/latest.jpg?a={time.time()}", use_container_width=True)
            cols[i%2].markdown(f"**{task_status}{bat_status}{mag_status}{sat_status}{slam_status}**")
            cols[i%2].dataframe(df, column_config=column_config)
            #cols[i%2].map(df, latitude="Lat", longitude="Lon", size="5", use_container_width=False, width=100)
            i += 1


menu()
with st.sidebar:
    st.number_input(":heartbeat: **:red[Active Threshold (min)]**", step=1, min_value=1, key="inactivity_time", max_value=10)
    st.number_input(":stopwatch: **:green[Refresh Rate (sec)]**", step=1, min_value=1, key="refresh_rate", max_value=5)
st.header(f":helicopter: **:orange[Active Drones]** (last {st.session_state.inactivity_time} mins)")
plot_data()