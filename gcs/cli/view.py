#!/usr/bin/env python3
import argparse
import sys
from typing import Dict, List

import cv2
import numpy as np
import zmq

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from steeleagle_sdk.protocol.messages.telemetry_pb2 import Frame


def load_drones_from_toml(config_path: str) -> List[Dict]:
    """Load drone configurations from a TOML file."""
    with open(config_path, "rb") as f:
        config = tomllib.load(f)
    return config.get("drones", [])


def main(drone_configs: List[Dict], rgb_mode: bool = False):
    """
    Subscribe to imagery frames from multiple drones and display in a grid.

    Args:
        drone_configs: List of dicts with 'name' and 'imagery' keys
        rgb_mode: If True, convert RGB to BGR for OpenCV display
    """
    ctx = zmq.Context.instance()

    # Create a poller for non-blocking recv from multiple sockets
    poller = zmq.Poller()

    # Connect to all drone imagery streams
    sockets = {}
    for drone in drone_configs:
        name = drone["name"]
        addr = drone["imagery"]
        sock = ctx.socket(zmq.SUB)
        sock.connect(addr)
        sock.setsockopt_string(zmq.SUBSCRIBE, "")
        sock.setsockopt(zmq.RCVTIMEO, 100)  # 100ms timeout
        sockets[name] = sock
        poller.register(sock, zmq.POLLIN)
        print(f"[viewer] {name}: Connected to {addr}")

    # Store latest frames for each drone
    frames: Dict[str, np.ndarray] = {}

    # Create window
    win = "Multi-Drone Viewer (press 'q' to quit)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    print(f"\n[viewer] Displaying {len(drone_configs)} drone(s). Press 'q' to quit.\n")

    try:
        while True:
            # Poll all sockets
            events = dict(poller.poll(timeout=50))

            for name, sock in sockets.items():
                if sock in events and events[sock] == zmq.POLLIN:
                    try:
                        parts = sock.recv_multipart(zmq.NOBLOCK)
                        if len(parts) == 1:
                            data = parts[0]
                        else:
                            _, data = parts[:2]

                        raw_frame = Frame()
                        raw_frame.ParseFromString(data)

                        frame_bytes = np.frombuffer(raw_frame.data, dtype=np.uint8)

                        expected = raw_frame.v_res * raw_frame.h_res * raw_frame.channels
                        if frame_bytes.size != expected:
                            print(
                                f"[{name}] Size mismatch: got {frame_bytes.size}, expected {expected}",
                                file=sys.stderr,
                            )
                            continue

                        img = frame_bytes.reshape(
                            raw_frame.v_res,
                            raw_frame.h_res,
                            raw_frame.channels,
                        )

                        if rgb_mode:
                            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

                        # Add drone name label
                        img_labeled = img.copy()
                        cv2.putText(
                            img_labeled,
                            name,
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1.0,
                            (0, 255, 0),
                            2,
                        )

                        frames[name] = img_labeled

                    except zmq.Again:
                        pass
                    except Exception as e:
                        print(f"[{name}] Error: {e}", file=sys.stderr)

            # Build grid display from available frames
            if frames:
                display = build_grid(frames, drone_configs)
                if display is not None:
                    cv2.imshow(win, display)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

    except KeyboardInterrupt:
        print("\n[viewer] Interrupted, exiting...")
    finally:
        cv2.destroyAllWindows()
        for sock in sockets.values():
            poller.unregister(sock)
            sock.close()


def build_grid(frames: Dict[str, np.ndarray], drone_configs: List[Dict]) -> np.ndarray:
    """
    Build a grid layout of all drone frames.
    Arranges frames in rows to create an approximately square grid.
    """
    n = len(drone_configs)
    if n == 0:
        return None

    # Calculate grid dimensions
    cols = int(np.ceil(np.sqrt(n)))
    rows = int(np.ceil(n / cols))

    # Get target size (use first available frame as reference)
    target_h, target_w = 480, 640
    for name in [d["name"] for d in drone_configs]:
        if name in frames:
            target_h, target_w = frames[name].shape[:2]
            break

    # Create placeholder for missing frames
    placeholder = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    cv2.putText(
        placeholder,
        "No Signal",
        (target_w // 4, target_h // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (100, 100, 100),
        2,
    )

    # Build grid row by row
    grid_rows = []
    for row in range(rows):
        row_frames = []
        for col in range(cols):
            idx = row * cols + col
            if idx < n:
                name = drone_configs[idx]["name"]
                if name in frames:
                    frame = frames[name]
                    # Resize if needed
                    if frame.shape[:2] != (target_h, target_w):
                        frame = cv2.resize(frame, (target_w, target_h))
                    row_frames.append(frame)
                else:
                    # Show placeholder with drone name
                    ph = placeholder.copy()
                    cv2.putText(
                        ph,
                        name,
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0,
                        (100, 100, 100),
                        2,
                    )
                    row_frames.append(ph)
            else:
                # Empty cell for incomplete grid
                row_frames.append(np.zeros((target_h, target_w, 3), dtype=np.uint8))

        grid_rows.append(np.hstack(row_frames))

    return np.vstack(grid_rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Multi-Drone Viewer",
        description="Subscribe to imagery frames from multiple drones and display in a grid",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Path to TOML config file with drone definitions. "
             "Example: -c drones.toml",
    )
    parser.add_argument(
        "-i",
        "--imagery-addrs",
        nargs="+",
        default=None,
        help="ZMQ SUB addresses for imagery (alternative to config file). "
             "Format: 'name=address' or just 'address'. "
             "Examples: -i drone1=ipc:///tmp/imagery1.sock drone2=ipc:///tmp/imagery2.sock",
    )
    parser.add_argument(
        "--rgb",
        action="store_true",
        help="Interpret incoming frames as RGB and convert to OpenCV BGR for display",
    )
    args = parser.parse_args()

    # Determine drone list from config file or command line args
    drone_configs = []

    if args.config:
        # Load from TOML config file
        try:
            toml_drones = load_drones_from_toml(args.config)
            for drone in toml_drones:
                drone_configs.append({
                    "name": drone["name"],
                    "imagery": drone["imagery"],
                })
            print(f"Loaded {len(drone_configs)} drone(s) from {args.config}")
        except Exception as e:
            print(f"Error loading config file {args.config}: {e}")
            sys.exit(1)
    elif args.imagery_addrs:
        # Parse from command line arguments
        for i, addr in enumerate(args.imagery_addrs):
            if "=" in addr:
                name, address = addr.split("=", 1)
            else:
                name = f"drone{i}"
                address = addr
            drone_configs.append({"name": name, "imagery": address})
    else:
        # Default single drone
        drone_configs.append({
            "name": "drone0",
            "imagery": "ipc:///tmp/imagery.sock",
        })

    if not drone_configs:
        print("No drones configured. Use -c or -i to specify drones.")
        sys.exit(1)

    main(drone_configs, rgb_mode=args.rgb)
