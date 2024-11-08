# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import folium
import streamlit as st
from streamlit_folium import st_folium
from folium.plugins import MiniMap, Draw, Geocoder
from streamlit_ace import st_ace
from util import menu, authenticated

sample="""#Sample Mission
Task {
    Test tri {
        way_points: <Triangle>,
        gimbal_pitch: -20.0,
        drone_rotation: 0.0,
        sample_rate: 2,
        hover_delay: 0,
        model: coco,
        hsv_lower_bound: (30, 100, 100),
        hsv_upper_bound: (50, 255, 255)
    }

    Test rect {
        way_points: <Rectangle>,
        gimbal_pitch: -20.0,
        drone_rotation: 0.0,
        sample_rate: 2,
        hover_delay: 0,
        model: coco,
        hsv_lower_bound: (30, 100, 100),
        hsv_upper_bound: (50, 255, 255)
    }
}

Mission {
    Start tri
    Transition (timeout(10)) tri -> rect
    Transition (done) rect -> tri
}

"""

if "map_server" not in st.session_state:
    st.session_state.map_server = "Google Hybrid"
if "drawing" not in st.session_state:
    st.session_state.drawing = None
if "select_schema" not in st.session_state:
    st.session_state.select_schema = None
if "barfi_result" not in st.session_state:
    st.session_state.barfi_result = None
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

if not authenticated():
    st.stop()  # Do not continue if not authenticated

menu()
tiles_col = st.columns(5)
tiles_col[0].selectbox(
    key="map_server",
    label=":world_map: :blue[Tile Server]",
    options=("Google Sat", "Google Hybrid"),
)
if st.session_state.map_server == "Google Sat":
    tileset = "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga"
elif st.session_state.map_server == "Google Hybrid":
    tileset = "https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}&s=Ga"

tiles = folium.TileLayer(
    name=st.session_state.map_server, tiles=tileset, attr="Google", max_zoom=20
)


m = folium.Map(
    location=[40.415428612484924, -79.95028831875038],
    zoom_start=18,
    tiles=tiles,
    control_scale=True
)

Draw(export=True, ).add_to(m)
#Geocoder().add_to(m)
#MiniMap(toggle_display=True, tile_layer=tiles).add_to(m)

folium.LayerControl().add_to(m)
c1, c2 = st.columns(spec=[0.5, 0.5], gap="small")
with c1:
    st.session_state.drawing = st_folium(
        m,
        key="planning_map",
        use_container_width=True,
        height=600
    )

with c2:
    dsl = st_ace(height=600, value=sample, language="yaml")