#!/usr/bin/env python3
"""Serve synthetic per-vehicle JPEG frames for testing the GCS video stream.

The GCS backend's imagery broadcaster (_remote_imagery_broadcaster in
app/api.py) polls `{webserver}/raw/<vehicle>/latest.jpg` about 10x/sec and
forwards each frame over /ws/imagery/remote/<vehicle> to the frontend --
it does not read imagery from Redis, so mock_vehicles.py alone leaves the
video panel showing "nostream.png" forever. This script serves that same
HTTP path so any vehicle name (mock or real) gets a synthetic frame:
a color-hashed background (matching the frontend's own per-vehicle
coloring), the vehicle's name, and a moving dot + frame counter so it's
visibly live rather than a static image.

Usage:
    cd gcs/react/backend
    uv run scripts/mock_imagery_server.py                 # reads host:port from config.toml's webserver
    uv run scripts/mock_imagery_server.py --port 8080
"""

import argparse
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import cv2
import numpy as np
import toml
from colorhash import ColorHash

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.toml"
FRAME_WIDTH = 640
FRAME_HEIGHT = 480


def load_webserver_host_port(config_path: Path) -> tuple[str, int]:
    cfg = toml.load(config_path)
    backends = cfg["backend"]
    # Mirrors gcs/react/backend/app/api.py's lifespan startup: pick the
    # BACKEND env var's block if set, otherwise the first block in the file.
    key = os.getenv("BACKEND") or next(iter(backends))
    parsed = urlparse(backends[key]["webserver"])
    return parsed.hostname or "localhost", parsed.port or 8080


def make_frame(vehicle: str, frame_number: int) -> bytes:
    r, g, b = ColorHash(vehicle).rgb
    img = np.full((FRAME_HEIGHT, FRAME_WIDTH, 3), (b, g, r), dtype=np.uint8)

    cv2.putText(
        img,
        vehicle,
        (20, FRAME_HEIGHT // 2 - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        img,
        f"frame {frame_number}  {time.strftime('%H:%M:%S')}",
        (20, FRAME_HEIGHT // 2 + 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    # Bounces left-to-right so motion is visible even between same-second frames.
    span = FRAME_WIDTH - 40
    pos = frame_number * 7 % (span * 2)
    x = pos if pos <= span else span * 2 - pos
    cv2.circle(img, (x + 20, FRAME_HEIGHT - 40), 15, (255, 255, 255), -1)

    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise RuntimeError("failed to encode mock frame")
    return buf.tobytes()


class MockImageryHandler(BaseHTTPRequestHandler):
    frame_counters: dict[str, int] = {}

    def log_message(self, fmt, *args):
        pass  # polled ~10x/sec per connected vehicle; keep stdout quiet

    def do_GET(self):
        # Expected path: /raw/<vehicle>/latest.jpg (query string ignored)
        parts = self.path.split("?", 1)[0].strip("/").split("/")
        if len(parts) != 3 or parts[0] != "raw" or parts[2] != "latest.jpg":
            self.send_response(404)
            self.end_headers()
            return
        vehicle = parts[1]
        MockImageryHandler.frame_counters[vehicle] = (
            MockImageryHandler.frame_counters.get(vehicle, 0) + 1
        )
        jpeg_bytes = make_frame(vehicle, MockImageryHandler.frame_counters[vehicle])
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(jpeg_bytes)))
        self.end_headers()
        self.wfile.write(jpeg_bytes)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"Path to backend config.toml (default: {DEFAULT_CONFIG})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Override the port to listen on (default: parsed from config.toml's webserver)",
    )
    args = parser.parse_args()

    if not args.config.exists():
        sys.exit(
            f"Config file not found: {args.config}\n"
            f"Copy config.toml.template to config.toml in gcs/react/backend/ first."
        )

    host, port = load_webserver_host_port(args.config)
    if args.port is not None:
        port = args.port

    server = ThreadingHTTPServer((host, port), MockImageryHandler)
    print(
        f"Serving mock vehicle imagery at http://{host}:{port}/raw/<vehicle>/latest.jpg"
    )
    print(
        "Start the GCS backend and mock_vehicles.py separately, then select a vehicle's video feed to see it."
    )
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
