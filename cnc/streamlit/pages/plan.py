# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import streamlit as st
import streamlit.components.v1 as components
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from streamlit_ace import st_ace
from streamlit_oauth import OAuth2Component
from util import authenticated, menu

sample = """Task {
    Detect patrol_route {
        way_points: <Hex>,
        gimbal_pitch: -30.0,
        drone_rotation: 0.0,
        sample_rate: 2,
        hover_delay: 0,
        model: coco,
        hsv_lower_bound: (165, 60, 40),
        hsv_upper_bound: (180, 255, 255)
    }
    Track tracking {
        gimbal_pitch: -30.0,
        model: coco,
        class: person,
        hsv_lower_bound: (165, 60, 40),
        hsv_upper_bound: (180, 255, 255)
    }
}
Mission {
    Start patrol_route
    Transition ( hsv_detection( person ) ) patrol_route -> tracking
    Transition (done) tracking -> patrol_route
    Transition (done) patrol_route -> patrol_route
}
"""

if "map_server" not in st.session_state:
    st.session_state.map_server = "Google Hybrid"
if "file_list" not in st.session_state:
    st.session_state.file_list = {}

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


def fetch_mymaps():
    creds = Credentials(
        st.session_state.auth["token"]["access_token"],
        refresh_token=st.session_state.auth["token"]["refresh_token"],
        token_uri=st.secrets.oauth.token_endpoint,
        client_id=st.secrets.oauth.client_id,
        client_secret=st.secrets.oauth.client_secret,
    )

    if creds and not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    try:
        service = build("drive", "v3", credentials=creds)
        files = []
        results = (
            service.files()
            .list(
                q="mimeType = 'application/vnd.google-apps.map' and visibility = 'anyoneWithLink'",
                fields="nextPageToken, files(id, name)",
                pageSize=20,
            )
            .execute()
        )
        items = results.get("files", [])

        for file in items:
            st.session_state.file_list[file["id"]] = file["name"]
    except HttpError as error:
        st.error(f"An error occurred fetching files from Google Drive: {error}")


menu()
c1, c2 = st.columns(spec=[0.5, 0.5], gap="small")
with c1:
    if "auth" not in st.session_state:
        # create a button to start the OAuth2 flow
        oauth2 = OAuth2Component(
            st.secrets.oauth.client_id,
            st.secrets.oauth.client_secret,
            st.secrets.oauth.auth_endpoint,
            st.secrets.oauth.token_endpoint,
            st.secrets.oauth.token_endpoint,
            st.secrets.oauth.revoke_endpoint,
        )
        result = oauth2.authorize_button(
            name="Log in to Google Drive",
            icon="https://www.google.com/favicon.ico",
            redirect_uri=st.secrets.oauth.redirect_endpoint,
            scope=st.secrets.oauth.scope,
            key="google",
            extras_params={"prompt": "consent", "access_type": "offline"},
            use_container_width=True,
            pkce="S256",
        )

        if result:
            st.session_state.auth = result
            st.rerun()

    else:
        fetch_mymaps()
        st.selectbox(
            label=":world_map: **:blue[Load Map]**",
            options=st.session_state.file_list.keys(),
            format_func=lambda option: st.session_state.file_list[option],
            key="map_id",
            placeholder="Select a map to load from MyMaps...",
        )
        components.iframe(
            f"https://www.google.com/maps/d/u/0/embed?mid={st.session_state.map_id}",
            height=600,
            scrolling=True,
        )
        st.link_button(
            label="Download KML",
            type="primary",
            url=f"https://www.google.com/maps/d/kml?mid={st.session_state.map_id}&forcekml=1",
        )
        st.link_button(
            label="Edit in MyMaps",
            type="primary",
            url=f"https://www.google.com/maps/d/u/0/edit?mid={st.session_state.map_id}",
        )

with c2:
    st.subheader(":clipboard: **:green[Edit Mission Script]**", divider="gray")
    dsl = st_ace(height=600, value=sample, language="yaml")
    st.download_button(
        label="Download Mission File", data=dsl, file_name="mission.dsl", type="primary"
    )
