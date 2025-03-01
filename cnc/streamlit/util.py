# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import hmac
import json
import time

import pandas as pd
import redis
import streamlit as st
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

COLORS = [
    "red",
    "blue",
    "green",
    "purple",
    "orange",
    "darkred",
    "darkblue",
    "darkgreen",
    "pink",
    "beige",
    "lightred",
    "lightblue",
    "lightgreen",
    "darkpurple",
    "gray",
    "cadetblue",
    "lightgray",
    "black",
]

if "control_pressed" not in st.session_state:
    st.session_state.control_pressed = False
if "inactivity_time" not in st.session_state:
    st.session_state.inactivity_time = 1  # min


def authenticated():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store the password.
        else:
            st.session_state["password_correct"] = False

    # Return True if the password is validated.
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password.
    a, b, c = st.columns(3)
    b.text_input(
        "Password",
        type="password",
        on_change=password_entered,
        key="password",
    )
    if "password_correct" in st.session_state:
        b.error("Authentication failed.", icon=":material/block:")
    return False


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
def connect_redis_publisher():
    red = redis.Redis(
        host=st.secrets.redis,
        port=st.secrets.redis_port,
        username=st.secrets.redis_user,
        password=st.secrets.redis_pw,
    )
    subscriber = red.pubsub(ignore_subscribe_messages=True)
    return subscriber


@st.cache_resource
def connect_zmq():
    ctx = zmq.Context()
    z = ctx.socket(zmq.REQ)
    z.connect(f"tcp://{st.secrets.zmq}:{st.secrets.zmq_port}")
    return z


def get_drones():
    l = {}
    red = connect_redis()
    for k in red.keys("telemetry.*"):
        latest_entry = red.xrevrange(f"{k}", "+", "-", 1)
        last_update = int(latest_entry[0][0].split("-")[0]) / 1000
        if time.time() - last_update < st.session_state.inactivity_time * 60:  # minutes -> seconds
            l[f"{k.split('.')[-1]}"] = (
                f"**{k.split('.')[-1]}** "  # TODO: add :material/abc:[drone model] once it is sent with telemetry
            )

    return l


def stream_to_dataframe(results, types=DATA_TYPES) -> pd.DataFrame:
    _container = {}
    for item in results:
        _container[item[0]] = json.loads(json.dumps(item[1]))

    df = pd.DataFrame.from_dict(_container, orient="index")
    if types is not None:
        df = df.astype(types)

    return df


def control_drone(drone):
    st.session_state.selected_drone = drone
    st.session_state.control_pressed = True


def menu(with_control=True):
    st.sidebar.page_link("overview.py", label=":satellite_antenna: Overview")
    st.sidebar.page_link("pages/plan.py", label=":ledger: Mission Planning")
