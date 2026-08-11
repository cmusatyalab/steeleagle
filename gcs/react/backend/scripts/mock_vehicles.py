#!/usr/bin/env python3
"""Write mock vehicle telemetry into Redis for testing the GCS frontend.

Populates the same two Redis keys per vehicle that the real telemetry
engine writes, and that gcs/react/backend's /api/remote/vehicles endpoint
reads:

  - vehicle:<name>   (HASH)   slow-changing status: model, mag warning,
                               last-seen timestamp, home position.
  - telemetry:<name> (STREAM) fast-changing telemetry: position, bearing,
                               battery, sats, body velocity.

No swarm-controller or vehicle driver needs to be running for this --
/api/remote/vehicles reads Redis directly. Start the GCS backend
separately (`uv run main.py` in gcs/react/backend) to see these vehicles
in the UI.

Vehicle names are all prefixed (default "mock-drone-") so --cleanup can
safely remove only the keys this script created, without ever touching
real vehicle data.

Usage:
    cd gcs/react/backend
    uv run scripts/mock_vehicles.py                  # 3 vehicles, updates every 1s until Ctrl+C
    uv run scripts/mock_vehicles.py --count 5
    uv run scripts/mock_vehicles.py --once            # single snapshot, then exit
    uv run scripts/mock_vehicles.py --cleanup         # remove all mock-drone-* keys
"""

import argparse
import math
import os
import signal
import sys
import time
from pathlib import Path

import redis
import toml

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.toml"

# Matches Mapbox.jsx's hardcoded initial map center (center: [-79.94299,
# 40.44353]) so mock vehicles show up on screen without panning.
DEFAULT_CENTER_LAT = 40.44353
DEFAULT_CENTER_LONG = -79.94299

MODELS = ["parrot_anafi", "dji_mavic3", "parrot_anafi_usa"]


def load_redis_config(config_path: Path) -> dict:
    cfg = toml.load(config_path)
    backends = cfg["backend"]
    # Mirrors gcs/react/backend/app/api.py's lifespan startup: pick the
    # BACKEND env var's block if set, otherwise the first block in the file.
    key = os.getenv("BACKEND") or next(iter(backends))
    return backends[key]


def connect(config_path: Path) -> redis.Redis:
    backend = load_redis_config(config_path)
    return redis.Redis(
        host=backend["redis_host"],
        port=backend["redis_port"],
        username=backend["redis_username"],
        password=backend["redis_password"],
        decode_responses=True,
    )


class MockVehicle:
    """Deterministic per-vehicle profile and simple circular motion.

    /api/remote/vehicles currently passes the telemetry stream's `sats`
    field straight through to the frontend rather than the 0/1/2 GPS
    warning enum the real driver stores separately in the vehicle hash
    (a backend bug, not a mock-script quirk) -- so a raw satellite count
    like "11" would never trigger the frontend's warning/danger coloring.
    Writing enum-shaped 0/1/2 values directly here is what actually
    exercises Status.jsx's color logic; it isn't a realistic satellite
    count.
    """

    def __init__(self, name: str, index: int, center_lat: float, center_long: float):
        self.name = name
        self.model = MODELS[index % len(MODELS)]
        self.mag = 1 if index % 4 == 3 else 0  # every 4th vehicle: magnetometer warning
        self.sats = index % 3  # cycles 0 (good) / 1 (warning) / 2 (danger)
        self.battery = max(10, 95 - index * 18)
        # Small, distinct orbit per vehicle so markers don't overlap and
        # bearing visibly changes over time (exercises marker rotation).
        self.center_lat = center_lat + (index * 0.0015)
        self.center_long = center_long + (index * 0.0015)
        self.radius_deg = 0.0025
        self.angular_speed = 0.03 + index * 0.015  # radians/sec: slow, visible drift
        self.phase = index * (2 * math.pi / 5)
        self.forward_speed = 1.5 + index * 0.4  # m/s, cosmetic only
        self.altitude = 10.0 + index * 2.0
        self.start_time = time.time()

    def hash_fields(self) -> dict:
        return {
            "model": self.model,
            "mag": str(self.mag),
            "last_seen": str(time.time()),
            "position_info.home_lat": str(self.center_lat),
            "position_info.home_long": str(self.center_long),
            "position_info.home_alt": "0.0",
        }

    def stream_fields(self) -> dict:
        t = time.time() - self.start_time
        theta = self.phase + t * self.angular_speed
        lat = self.center_lat + self.radius_deg * math.sin(theta)
        long = self.center_long + self.radius_deg * math.cos(theta)
        # Heading of travel around the circle, degrees clockwise from north.
        bearing = (math.degrees(theta) + 90) % 360
        self.battery = max(1, self.battery - 0.02)
        return {
            "latitude": str(lat),
            "longitude": str(long),
            "rel_altitude": str(self.altitude),
            "bearing": str(round(bearing, 1)),
            # Vehicle.battery is a NonNegativeInt on the backend -- a
            # "95.0"-style string fails pydantic's int coercion and gets
            # the whole vehicle skipped. self.battery decays as a float
            # internally for smooth-looking drain; only the wire value
            # needs to be integer-shaped.
            "battery": str(round(self.battery)),
            "sats": str(self.sats),
            "v_body_forward": str(self.forward_speed),
            "v_body_lateral": "0.0",
            "v_body_altitude": "0.0",
            "v_body_angular": str(round(math.degrees(self.angular_speed), 1)),
        }


def write_vehicle(r: redis.Redis, v: MockVehicle) -> None:
    r.hset(f"vehicle:{v.name}", mapping=v.hash_fields())
    r.xadd(f"telemetry:{v.name}", v.stream_fields(), maxlen=1000, approximate=True)


def cleanup(r: redis.Redis, prefix: str) -> None:
    names = set()
    for key in r.keys(f"vehicle:{prefix}*"):
        names.add(key.split(":", 1)[1])
    for key in r.keys(f"telemetry:{prefix}*"):
        names.add(key.split(":", 1)[1])
    if not names:
        print(f"No mock vehicles found with prefix {prefix!r}.")
        return
    pipe = r.pipeline()
    for name in names:
        pipe.delete(f"vehicle:{name}", f"telemetry:{name}")
    pipe.execute()
    print(f"Removed {len(names)} mock vehicle(s): {', '.join(sorted(names))}")


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
        "--count", type=int, default=3, help="Number of mock vehicles (default: 3)"
    )
    parser.add_argument(
        "--prefix",
        default="mock-drone-",
        help="Vehicle name prefix (default: mock-drone-)",
    )
    parser.add_argument("--center-lat", type=float, default=DEFAULT_CENTER_LAT)
    parser.add_argument("--center-long", type=float, default=DEFAULT_CENTER_LONG)
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between telemetry updates (default: 1.0)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Write a single snapshot and exit instead of looping",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete all mock vehicles matching --prefix and exit",
    )
    args = parser.parse_args()

    if not args.config.exists():
        sys.exit(
            f"Config file not found: {args.config}\n"
            f"Copy config.toml.template to config.toml in gcs/react/backend/ first."
        )

    r = connect(args.config)
    try:
        r.ping()
    except redis.exceptions.ConnectionError as e:
        sys.exit(f"Could not connect to Redis using {args.config}: {e}")

    if args.cleanup:
        cleanup(r, args.prefix)
        return

    vehicles = [
        MockVehicle(f"{args.prefix}{i + 1}", i, args.center_lat, args.center_long)
        for i in range(args.count)
    ]
    print(
        f"Writing {len(vehicles)} mock vehicle(s) to Redis: {', '.join(v.name for v in vehicles)}"
    )
    print(
        "Start the GCS backend separately (uv run main.py in gcs/react/backend) to see them in the UI."
    )

    if args.once:
        for v in vehicles:
            write_vehicle(r, v)
        print(
            "Wrote one snapshot. Vehicles will show 'Disconnected' after 5s without "
            "further updates -- re-run without --once for continuous simulated movement."
        )
        return

    print(f"Updating every {args.interval}s. Press Ctrl+C to stop.")
    stop = False

    def handle_sigint(signum, frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, handle_sigint)
    while not stop:
        for v in vehicles:
            write_vehicle(r, v)
        time.sleep(args.interval)

    print(
        "\nStopped. Mock vehicles will show as 'Disconnected' after 5s of no updates."
    )
    print(
        f"Run with --cleanup --prefix {args.prefix!r} to remove them from Redis entirely."
    )


if __name__ == "__main__":
    main()
