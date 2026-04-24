#!/usr/bin/env python3
import argparse
import asyncio
import contextlib
import json
import os
import select
import sys
import threading
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Set

try:
    import tomllib
except ImportError:
    import tomli as tomllib

import grpc
from steeleagle_sdk.dsl import build_mission

# Protocol imports
from steeleagle_sdk.protocol.services.control_service_pb2 import (
    HoldRequest,
    JoystickRequest,
    LandRequest,
    TakeOffRequest,
)
from steeleagle_sdk.protocol.services.control_service_pb2_grpc import ControlStub
from steeleagle_sdk.protocol.services.mission_service_pb2 import (
    StartRequest,
    StopRequest,
    UploadRequest,
)
from steeleagle_sdk.protocol.services.mission_service_pb2_grpc import MissionStub

IDENTITY_MD = (("identity", "server"),)


@dataclass
class DroneConnection:
    """Represents a connection to a single drone."""
    name: str
    address: str
    channel: grpc.aio.Channel = None
    control_stub: ControlStub = None
    mission_stub: MissionStub = None
    connected: bool = False


@dataclass
class DroneManager:
    """Manages multiple drone connections and tracks which ones are currently selected."""
    drones: Dict[str, DroneConnection] = field(default_factory=dict)
    selected_indices: Set[int] = field(default_factory=set)

    def get_drone_list(self) -> List[DroneConnection]:
        """Return drones as an ordered list for index-based access."""
        return list(self.drones.values())

    def get_selected_drones(self) -> List[DroneConnection]:
        """Return currently selected drones."""
        drone_list = self.get_drone_list()
        return [drone_list[i] for i in sorted(self.selected_indices) if i < len(drone_list)]

    def select_drones(self, indices: Set[int]):
        """Update the set of selected drones by index."""
        drone_list = self.get_drone_list()
        valid_indices = {i for i in indices if 0 <= i < len(drone_list)}
        self.selected_indices = valid_indices

    def select_by_names(self, names: List[str]):
        """Select drones by their names."""
        drone_list = self.get_drone_list()
        indices = set()
        for name in names:
            for i, drone in enumerate(drone_list):
                if drone.name.lower() == name.lower():
                    indices.add(i)
                    break
        self.selected_indices = indices

    def get_status_string(self) -> str:
        """Return a status string showing all drones and their selection status."""
        drone_list = self.get_drone_list()
        lines = []
        for i, drone in enumerate(drone_list):
            selected = "✓" if i in self.selected_indices else " "
            connected = "connected" if drone.connected else "disconnected"
            lines.append(f"  [{selected}] {i}: {drone.name} ({drone.address}) - {connected}")
        return "\n".join(lines)


# --------- raw TTY helpers (WSL-friendly) ---------
class TTYMode:
    def __init__(self):
        self.fd = sys.stdin.fileno()
        self._orig = None
        self._supported = sys.stdin.isatty()

    def raw(self):
        if not self._supported:
            return
        import termios
        import tty

        if self._orig is None:
            self._orig = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)

    def cooked(self):
        if not self._supported or self._orig is None:
            return
        import termios

        termios.tcsetattr(self.fd, termios.TCSADRAIN, self._orig)


def listen_for_keys(
    key_queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
    paused: threading.Event,
    stop_evt: threading.Event,
):
    """
    Read single characters from stdin in raw mode and push to the asyncio queue.
    This runs in a background thread.
    """
    fd = sys.stdin.fileno()
    while not stop_evt.is_set():
        if paused.is_set():
            # paused while main thread uses input()
            stop_evt.wait(0.02)
            continue
        r, _, _ = select.select([fd], [], [], 0.05)
        if not r:
            continue
        try:
            ch = os.read(fd, 1).decode(errors="ignore")
        except Exception:
            ch = ""
        if ch:
            loop.call_soon_threadsafe(key_queue.put_nowait, ch)


def print_controls(manager: DroneManager):
    """Print available controls and current drone selection."""
    print("\n" + "=" * 60)
    print("Controls: w/a/s/d (XY), i/k (Z), j/l (yaw), t=TakeOff, g=Land,")
    print("          ' ' (Hold), m=Start, n=Stop, c=Compile+Upload,")
    print("          p=Switch drones, q=Show status, Esc to quit")
    print("=" * 60)
    print("\nDrones:")
    print(manager.get_status_string())
    selected = manager.get_selected_drones()
    if selected:
        print(f"\nCurrently controlling: {', '.join(d.name for d in selected)}")
    else:
        print("\nNo drones selected! Press 'p' to select drones.")
    print("-" * 60 + "\n")


# --------- main consumer ---------
async def consume_keys(
    key_queue: asyncio.Queue,
    tty: TTYMode,
    paused: threading.Event,
    manager: DroneManager,
):
    print_controls(manager)

    while True:
        key = await key_queue.get()

        # Quit on ESC
        if key == "\x1b":  # ESC
            break

        async def _send_stream(drone: DroneConnection, call, command_name: str):
            try:
                # For server-streaming RPCs
                async for response in call:
                    print(f"[{drone.name}] Response for {command_name}: {response.status}")
            except grpc.aio.AioRpcError as e:
                print(f"[{drone.name}] Error during {command_name}: {e}")

        async def _send_unary(drone: DroneConnection, call, command_name: str):
            try:
                # assuming unary RPC that just acks
                await call
            except grpc.aio.AioRpcError as e:
                print(f"[{drone.name}] Error during {command_name}: {e}")

        selected_drones = manager.get_selected_drones()

        # Joystick
        if key in ["w", "a", "s", "d", "j", "i", "k", "l"]:
            if not selected_drones:
                print("No drones selected! Press 'p' to select drones.")
                continue
            print(f"Sending Joystick to {len(selected_drones)} drone(s)")
            for drone in selected_drones:
                if not drone.connected:
                    print(f"[{drone.name}] Not connected, skipping")
                    continue
                joystick = JoystickRequest()
                if key == "a":
                    joystick.velocity.y_vel = -5.0
                elif key == "d":
                    joystick.velocity.y_vel = 5.0
                elif key == "w":
                    joystick.velocity.x_vel = 5.0
                elif key == "s":
                    joystick.velocity.x_vel = -5.0
                elif key == "j":
                    joystick.velocity.angular_vel = -20.0
                elif key == "l":
                    joystick.velocity.angular_vel = 20.0
                elif key == "i":
                    joystick.velocity.z_vel = 5.0
                elif key == "k":
                    joystick.velocity.z_vel = -5.0

                call = drone.control_stub.Joystick(joystick, metadata=IDENTITY_MD)
                asyncio.create_task(_send_unary(drone, call, "joystick"))

        elif key == "t":  # TakeOff
            if not selected_drones:
                print("No drones selected! Press 'p' to select drones.")
                continue
            print(f"Sending TakeOff to {len(selected_drones)} drone(s)")
            for drone in selected_drones:
                if not drone.connected:
                    print(f"[{drone.name}] Not connected, skipping")
                    continue
                takeoff = TakeOffRequest()
                takeoff.take_off_altitude = 10.0
                call = drone.control_stub.TakeOff(takeoff, metadata=IDENTITY_MD)
                asyncio.create_task(_send_stream(drone, call, "takeoff"))

        elif key == "g":  # Land
            if not selected_drones:
                print("No drones selected! Press 'p' to select drones.")
                continue
            print(f"Sending Land to {len(selected_drones)} drone(s)")
            for drone in selected_drones:
                if not drone.connected:
                    print(f"[{drone.name}] Not connected, skipping")
                    continue
                land = LandRequest()
                call = drone.control_stub.Land(land, metadata=IDENTITY_MD)
                asyncio.create_task(_send_stream(drone, call, "land"))

        elif key == " ":  # Hold (space)
            if not selected_drones:
                print("No drones selected! Press 'p' to select drones.")
                continue
            print(f"Sending Hold to {len(selected_drones)} drone(s)")
            for drone in selected_drones:
                if not drone.connected:
                    print(f"[{drone.name}] Not connected, skipping")
                    continue
                hold = HoldRequest()
                call = drone.control_stub.Hold(hold, metadata=IDENTITY_MD)
                asyncio.create_task(_send_stream(drone, call, "hold"))

        elif key == "p":  # Switch/select drones
            paused.set()
            tty.cooked()
            try:
                print("\n" + "=" * 60)
                print("DRONE SELECTION")
                print("=" * 60)
                print("\nAvailable drones:")
                print(manager.get_status_string())
                print("\nEnter drone selection (comma-separated indices or names):")
                print("  Examples: '0,1,2' or 'drone1,drone2' or '0,drone2'")
                print("  Press Enter with no input to cancel.")
                selection = input("> ").strip()

                if selection:
                    # Parse the input - can be indices or names
                    parts = [p.strip() for p in selection.split(",")]
                    indices = set()
                    names = []

                    for part in parts:
                        if part.isdigit():
                            indices.add(int(part))
                        else:
                            names.append(part)

                    # Add indices from names
                    if names:
                        drone_list = manager.get_drone_list()
                        for name in names:
                            for i, drone in enumerate(drone_list):
                                if drone.name.lower() == name.lower():
                                    indices.add(i)
                                    break
                            else:
                                print(f"Warning: Drone '{name}' not found")

                    manager.select_drones(indices)
                    selected = manager.get_selected_drones()
                    if selected:
                        print(f"\nNow controlling: {', '.join(d.name for d in selected)}")
                    else:
                        print("\nNo valid drones selected.")
                else:
                    print("Selection cancelled.")
            finally:
                # Drain any buffered keys typed during prompts
                while not key_queue.empty():
                    with contextlib.suppress(Exception):
                        key_queue.get_nowait()
                        key_queue.task_done()
                # Back to raw mode + resume reader
                tty.raw()
                paused.clear()
                print_controls(manager)

        elif key == "q":  # Show status
            print_controls(manager)

        elif key == "c":  # Compile Mission (use input() in cooked mode)
            if not selected_drones:
                print("No drones selected! Press 'p' to select drones.")
                continue
            # Pause reader + switch to cooked so you can type
            paused.set()
            tty.cooked()
            try:
                kml_path = input("Choose a KML file: ").strip()
                dsl_path = input("Choose a DSL file: ").strip()

                try:
                    kml = open(kml_path, "rb").read()
                except Exception as e:
                    print(f"[Compile] Failed to read KML: {e}")
                    kml = None
                try:
                    dsl = open(dsl_path, encoding="utf-8").read()
                except Exception as e:
                    print(f"[Compile] Failed to read DSL: {e}")
                    dsl = None

                if kml is None or dsl is None:
                    pass
                else:
                    print("[Compile] Compiling DSL…")
                    mission = build_mission(dsl)
                    mission_json = json.dumps(asdict(mission))
                    print(mission_json)
                    if not mission_json:
                        print("[Compile] No responses.")
                    else:
                        print(f"[Compile] Uploading to {len(selected_drones)} drone(s)")
                        for drone in selected_drones:
                            if not drone.connected:
                                print(f"[{drone.name}] Not connected, skipping")
                                continue
                            upload = UploadRequest()
                            upload.mission.content = mission_json
                            upload.mission.map = kml
                            # Assuming Upload is unary or server-streaming:
                            call = drone.mission_stub.Upload(upload, metadata=IDENTITY_MD)
                            asyncio.create_task(_send_unary(drone, call, "upload"))
            finally:
                # Drain any buffered keys typed during prompts
                while not key_queue.empty():
                    with contextlib.suppress(Exception):
                        key_queue.get_nowait()
                        key_queue.task_done()
                # Back to raw mode + resume reader
                tty.raw()
                paused.clear()

        elif key == "m":  # Start Mission
            if not selected_drones:
                print("No drones selected! Press 'p' to select drones.")
                continue
            print(f"Sending Start to {len(selected_drones)} drone(s)")
            for drone in selected_drones:
                if not drone.connected:
                    print(f"[{drone.name}] Not connected, skipping")
                    continue
                start = StartRequest()
                call = drone.mission_stub.Start(start, metadata=IDENTITY_MD)
                asyncio.create_task(_send_unary(drone, call, "start"))

        elif key == "n":  # Stop Mission
            if not selected_drones:
                print("No drones selected! Press 'p' to select drones.")
                continue
            print(f"Sending Stop to {len(selected_drones)} drone(s)")
            for drone in selected_drones:
                if not drone.connected:
                    print(f"[{drone.name}] Not connected, skipping")
                    continue
                stop = StopRequest()
                call = drone.mission_stub.Stop(stop, metadata=IDENTITY_MD)
                asyncio.create_task(_send_unary(drone, call, "stop"))

        else:
            if key not in ("\n", "\r"):
                print(f"Key not recognized: {repr(key)}")


async def connect_drone(drone: DroneConnection) -> bool:
    """Attempt to connect to a single drone. Returns True if successful."""
    try:
        drone.channel = grpc.aio.insecure_channel(drone.address)
        await asyncio.wait_for(drone.channel.channel_ready(), timeout=5.0)
        drone.control_stub = ControlStub(drone.channel)
        drone.mission_stub = MissionStub(drone.channel)
        drone.connected = True
        print(f"[{drone.name}] Connected to {drone.address}")
        return True
    except Exception as e:
        print(f"[{drone.name}] Could not connect to {drone.address}: {e}")
        drone.connected = False
        return False


async def main(args):
    key_queue: asyncio.Queue[str] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    tty = TTYMode()

    paused = threading.Event()
    stop_evt = threading.Event()

    # Create drone connections from parsed configs
    manager = DroneManager()

    for drone_cfg in args.drone_configs:
        drone = DroneConnection(name=drone_cfg["name"], address=drone_cfg["address"])
        manager.drones[drone_cfg["name"]] = drone

    # Connect to all drones
    print("Connecting to drones...")
    connect_tasks = [connect_drone(drone) for drone in manager.get_drone_list()]
    await asyncio.gather(*connect_tasks)

    # Select all connected drones by default
    connected_indices = {i for i, d in enumerate(manager.get_drone_list()) if d.connected}
    manager.select_drones(connected_indices)

    if not any(d.connected for d in manager.get_drone_list()):
        print("No drones connected. Exiting.")
        return

    tty.raw()

    listener_thread = threading.Thread(
        target=listen_for_keys,
        args=(key_queue, loop, paused, stop_evt),
        daemon=True,
    )
    listener_thread.start()

    try:
        await consume_keys(key_queue, tty, paused, manager)
    finally:
        stop_evt.set()
        tty.cooked()
        # Close all channels
        for drone in manager.get_drone_list():
            if drone.channel:
                await drone.channel.close()


def load_drones_from_toml(config_path: str) -> List[Dict]:
    """Load drone configurations from a TOML file."""
    with open(config_path, "rb") as f:
        config = tomllib.load(f)
    return config.get("drones", [])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="CLI Commander",
        description="Gives a CLI interface to control multiple vehicles (WSL-friendly)",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Path to TOML config file with drone definitions. "
             "Example: -c drones.toml",
    )
    parser.add_argument(
        "-a",
        "--addrs",
        nargs="+",
        default=None,
        help="Addresses of kernel services (alternative to config file). "
             "Format: 'name=address' or just 'address'. "
             "Examples: -a drone1=unix:///tmp/kernel1.sock drone2=unix:///tmp/kernel2.sock",
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
                    "address": drone["kernel"],
                })
            print(f"Loaded {len(drone_configs)} drone(s) from {args.config}")
        except Exception as e:
            print(f"Error loading config file {args.config}: {e}")
            sys.exit(1)
    elif args.addrs:
        # Parse from command line arguments
        for i, addr in enumerate(args.addrs):
            if "=" in addr:
                name, address = addr.split("=", 1)
            else:
                name = f"drone{i}"
                address = addr
            drone_configs.append({"name": name, "address": address})
    else:
        # Default single drone
        drone_configs.append({
            "name": "drone0",
            "address": "unix:///tmp/kernel.sock",
        })

    # Store parsed configs in args for main()
    args.drone_configs = drone_configs

    asyncio.run(main(args))
