#!/usr/bin/env python3
import asyncio
import json
import math

import folium
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

app = FastAPI()

# Center of your map
center = (40.41448, -79.94803)


def build_map_html() -> str:
    # 1) Build the folium map
    m = folium.Map(location=center, zoom_start=14, tiles="OpenStreetMap")
    folium.Marker(location=center, tooltip="Base").add_to(m)

    # 2) Get the JS variable name folium uses for the map
    map_name = m.get_name()  # e.g. "map_3c50d0a9701ac9381fa00a0e19247d7f"

    # 3) Render full HTML as a string
    html = m.get_root().render()

    # 4) JS that listens to /stream and moves a marker
    inject_js = f"""
<script>
let marker = null;

// Folium's map object (global var defined in its own <script>)
const map = {map_name};

function connectStream() {{
    console.log("Connecting to /stream...");
    const eventSource = new EventSource("/stream");

    eventSource.onmessage = function(event) {{
        const data = JSON.parse(event.data);
        const lat = data.lat;
        const lon = data.lon;

        console.log("New point:", lat, lon);

        // Remove old marker
        if (marker !== null) {{
            map.removeLayer(marker);
        }}

        // Add new marker at latest GPS
        marker = L.marker([lat, lon]).addTo(map);
    }};

    eventSource.onerror = function(err) {{
        console.error("EventSource error:", err);
    }};
}}

connectStream();
</script>
"""

    # 5) Inject JS *after* folium's map script, just before </html>
    if "</html>" in html:
        html = html.replace("</html>", inject_js + "\n</html>")
    else:
        html += inject_js

    return html


@app.get("/", response_class=HTMLResponse)
async def index():
    html = build_map_html()
    return HTMLResponse(html)


@app.get("/stream")
async def stream():
    async def event_generator():
        t = 0.0
        while True:
            # Simulate movement in a small circle around `center`
            R = 0.01
            lat = center[0] + R * math.sin(t)
            lon = center[1] + R * math.cos(t)

            payload = json.dumps({"lat": lat, "lon": lon})
            yield f"data: {payload}\n\n"

            await asyncio.sleep(0.3)
            t += 0.1

    return StreamingResponse(event_generator(), media_type="text/event-stream")
