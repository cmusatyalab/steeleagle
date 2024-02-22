# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import streamlit as st
import redis
import pandas as pd
import json
import zmq

DATA_TYPES = {
    "latitude": "float",
    "longitude": "float",
    "altitude": "float",
    "bearing": "int",
    "rssi": "int",
    "battery": "int",
    "mag": "int",
    # "sats": int,
}

if "control_pressed" not in st.session_state:
    st.session_state.control_pressed = False
@st.cache_resource
def connect_redis():
    red = redis.Redis(
        host=st.secrets.redis,
        port=st.secrets.redis_port,
        username=st.secrets.redis_user,
        password=st.secrets.redis_pw,
        decode_responses=True,
    )
    return red

@st.cache_resource
def connect_zmq():
    ctx = zmq.Context()
    z = ctx.socket(zmq.REQ)
    z.connect(f'tcp://{st.secrets.zmq}:{st.secrets.zmq_port}')
    return z


def get_drones():
    l = []
    red = connect_redis()
    for k in red.keys("telemetry.*"):
        l.append(k.split(".")[-1])
    return l

def stream_to_dataframe(results, types=DATA_TYPES ) -> pd.DataFrame:
    _container = {}
    for item in results:
        _container[item[0]] = json.loads(json.dumps(item[1]))

    df = pd.DataFrame.from_dict(_container, orient='index')
    if types is not None:
        df = df.astype(types)

    return df

def control_drone(drone):
    st.session_state.selected_drone = drone
    st.session_state.control_pressed = True


def menu(with_control=True):
    st.sidebar.page_link("overview.py", label="Overview")
    st.sidebar.page_link("pages/plan.py", label="Mission Planning (WIP)")
    if with_control:
        st.sidebar.header(":helicopter: Control", divider=True)
        for d in get_drones():
            #st.sidebar.page_link(f"pages/control.py", label=d)
            if "selected_drone" in st.session_state:
                if st.session_state.selected_drone == d and st.session_state.control_pressed:
                        st.session_state.control_pressed = False
                        st.switch_page("pages/control.py")
            st.sidebar.button(label=d, on_click=control_drone, args=[d])



