# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only
import folium
import streamlit as st
from streamlit_folium import st_folium
from folium.plugins import MiniMap
from util import  connect_redis,  menu, COLORS, authenticated
import datetime

if "map_server" not in st.session_state:
    st.session_state.map_server = "Google Hybrid"
if "center" not in st.session_state:
    st.session_state.center = [40.413552, -79.949152]

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


if not authenticated():
    st.stop()  # Do not continue if not authenticated

red = connect_redis()

@st.fragment(run_every="1s")
def draw_map():
    m = folium.Map(
        location=[40.415428612484924, -79.95028831875038],
        zoom_start=18,
        tiles=tiles,
    )

    MiniMap(toggle_display=True, tile_layer=tiles).add_to(m)
    fg = folium.FeatureGroup(name="Detected Objects")
    # Draw(export=True).add_to(m)
    lc = folium.LayerControl()

    marker_color = 0
    for obj in red.zrange("detections", 0, -1):
        if len(red.keys(f"objects:{obj}")) > 0:
            fields = red.hgetall(f"objects:{obj}")
            img_ref = f'<img src="{fields["link"]}" height="250px" width="250px"/>'
            div_content = f"""
                    <div style="color:white;font-size: 12pt;font-weight: bold;background-color:{COLORS[marker_color]};">
                        {obj}<br/>
                        {fields["confidence"]:.2f}<br/>
                        {fields["drone_id"]}<br/>
                        {datetime.datetime.fromtimestamp(fields["last_seen"])}
                    </div>
                """

            text = folium.DivIcon(
                icon_size="null", #set the size to null so that it expands to the length of the string inside in the div
                icon_anchor=(-20, 30),
                html=div_content,
            )
            object_icon = folium.Icon(
                icon="object-group",
                color=COLORS[marker_color],
                prefix="fa",
            )

            fg.add_child(
                folium.Marker(
                    location=[
                        fields["latitude"],
                        fields["longitude"],
                    ],
                    icon=object_icon,
                    tooltip=img_ref
                )
            )

            fg.add_child(
                folium.Marker(
                    location=[
                        fields["latitude"],
                        fields["longitude"],
                    ],
                    icon=text,
                    tooltip=img_ref
                )
            )

    st_folium(
        m,
        key="overview_map",
        use_container_width=True,
        feature_group_to_add=[fg],
        layer_control=lc,
        returned_objects=[],
        center=st.session_state.center,
        height=720
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
        index=0
    )

if st.session_state.map_server == "Google Sat":
    tileset = "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga"
elif st.session_state.map_server == "Google Hybrid":
    tileset = "https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}&s=Ga"

tiles = folium.TileLayer(
    name=st.session_state.map_server, tiles=tileset, attr="Google", max_zoom=23
)

st.caption("**:blue-background[:globe_with_meridians: Detected Objects]**")
draw_map()

