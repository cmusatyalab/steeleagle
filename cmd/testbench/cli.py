import argparse
import asyncio
import contextlib
import os
import select
import sys
import threading
import tomllib
from dataclasses import dataclass, field
from typing import Dict, List, Set

import cv2
import grpc
import numpy as np
from steeleagle_protocol.v1 import common_pb2
from steeleagle_protocol.v1.services.driver import control_pb2, control_pb2_grpc
from steeleagle_protocol.v1.services.mission import mission_pb2, mission_pb2_grpc
from steeleagle_protocol.v1.services.vehicle import data_pb2, data_pb2_grpc

# Target FPS for polling DataService.GetFrame to feed the video windows.
VIDEO_POLL_FPS = 15.0

# Name of the vehicle launched by `cmd/testbench/main.go`.
DEFAULT_VEHICLE_NAME = "test-vehicle"


def runtime_dir() -> str:
    """Mirror adrg/xdg's RuntimeDir default used by core/util.GetRuntimeDir."""
    return os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"


def vehicle_socket_address(name: str) -> str:
    """
    Compute the address of a vehicle's main services socket, following the
    layout defined by core/util.GetVehicleDirByName (steeleagle/vehicles/<name>).
    """
    path = os.path.join(runtime_dir(), "steeleagle", "vehicles", name, "server")
    return f"unix://{path}"


def resolve_address(value: str) -> str:
    """
    If `value` already looks like a URI (has a scheme), use it as-is.
    Otherwise, treat it as the name of a locally-running vehicle and resolve
    its main socket address.
    """
    if "://" in value:
        return value
    return vehicle_socket_address(value)


@dataclass
class DroneConnection:
    """Represents a connection to a single drone."""
    name: str
    address: str
    channel: grpc.aio.Channel = None
    control_stub: control_pb2_grpc.ControlServiceStub = None
    mission_stub: mission_pb2_grpc.MissionServiceStub = None
    data_stub: data_pb2_grpc.DataServiceStub = None
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
    print("          ' ' (Hold), m=Start Mission, n=Stop Mission,")
    print("          p=Switch drones, q=Show status, Esc to quit")
    print("=" * 60)
    print("A video feed window is opened per connected drone (DataService.GetFrame).")
    print("\nDrones:")
    print(manager.get_status_string())
    selected = manager.get_selected_drones()
    if selected:
        print(f"\nCurrently controlling: {', '.join(d.name for d in selected)}")
    else:
        print("\nNo drones selected! Press 'p' to select drones.")
    print("-" * 60 + "\n")


async def _send(drone: DroneConnection, call, command_name: str):
    try:
        await call
        print(f"[{drone.name}] {command_name} ok")
    except grpc.aio.AioRpcError as e:
        print(f"[{drone.name}] Error during {command_name}: {e.details()}")


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

        selected_drones = manager.get_selected_drones()

        # Velocity control
        if key in ["w", "a", "s", "d", "j", "i", "k", "l"]:
            if not selected_drones:
                print("No drones selected! Press 'p' to select drones.")
                continue
            print(f"Sending SetVelocity to {len(selected_drones)} drone(s)")
            for drone in selected_drones:
                if not drone.connected:
                    print(f"[{drone.name}] Not connected, skipping")
                    continue
                velocity = common_pb2.Velocity()
                if key == "a":
                    velocity.y_vel = -5.0
                elif key == "d":
                    velocity.y_vel = 5.0
                elif key == "w":
                    velocity.x_vel = 5.0
                elif key == "s":
                    velocity.x_vel = -5.0
                elif key == "j":
                    velocity.angular_vel = -20.0
                elif key == "l":
                    velocity.angular_vel = 20.0
                elif key == "i":
                    velocity.z_vel = 5.0
                elif key == "k":
                    velocity.z_vel = -5.0

                request = control_pb2.SetVelocityRequest(
                    velocity=velocity,
                    frame=control_pb2.REFERENCE_FRAME_BODY,
                )
                call = drone.control_stub.SetVelocity(request)
                asyncio.create_task(_send(drone, call, "SetVelocity"))

        elif key == "t":  # TakeOff
            if not selected_drones:
                print("No drones selected! Press 'p' to select drones.")
                continue
            print(f"Sending TakeOff to {len(selected_drones)} drone(s)")
            for drone in selected_drones:
                if not drone.connected:
                    print(f"[{drone.name}] Not connected, skipping")
                    continue
                request = control_pb2.TakeOffRequest(take_off_altitude=10.0)
                call = drone.control_stub.TakeOff(request)
                asyncio.create_task(_send(drone, call, "TakeOff"))

        elif key == "g":  # Land
            if not selected_drones:
                print("No drones selected! Press 'p' to select drones.")
                continue
            print(f"Sending Land to {len(selected_drones)} drone(s)")
            for drone in selected_drones:
                if not drone.connected:
                    print(f"[{drone.name}] Not connected, skipping")
                    continue
                request = control_pb2.LandRequest()
                call = drone.control_stub.Land(request)
                asyncio.create_task(_send(drone, call, "Land"))

        elif key == " ":  # Hold (space)
            if not selected_drones:
                print("No drones selected! Press 'p' to select drones.")
                continue
            print(f"Sending Hold to {len(selected_drones)} drone(s)")
            for drone in selected_drones:
                if not drone.connected:
                    print(f"[{drone.name}] Not connected, skipping")
                    continue
                request = control_pb2.HoldRequest()
                call = drone.control_stub.Hold(request)
                asyncio.create_task(_send(drone, call, "Hold"))

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

        elif key == "m":  # Start Mission
            if not selected_drones:
                print("No drones selected! Press 'p' to select drones.")
                continue
            print(f"Sending StartMission to {len(selected_drones)} drone(s)")
            for drone in selected_drones:
                if not drone.connected:
                    print(f"[{drone.name}] Not connected, skipping")
                    continue
                request = mission_pb2.StartMissionRequest()
                call = drone.mission_stub.StartMission(request)
                asyncio.create_task(_send(drone, call, "StartMission"))

        elif key == "n":  # Stop Mission
            if not selected_drones:
                print("No drones selected! Press 'p' to select drones.")
                continue
            print(f"Sending StopMission to {len(selected_drones)} drone(s)")
            for drone in selected_drones:
                if not drone.connected:
                    print(f"[{drone.name}] Not connected, skipping")
                    continue
                request = mission_pb2.StopMissionRequest()
                call = drone.mission_stub.StopMission(request)
                asyncio.create_task(_send(drone, call, "StopMission"))

        else:
            if key not in ("\n", "\r"):
                print(f"Key not recognized: {repr(key)}")


async def connect_drone(drone: DroneConnection) -> bool:
    """Attempt to connect to a single drone. Returns True if successful."""
    try:
        drone.channel = grpc.aio.insecure_channel(drone.address)
        await asyncio.wait_for(drone.channel.channel_ready(), timeout=5.0)
        drone.control_stub = control_pb2_grpc.ControlServiceStub(drone.channel)
        drone.mission_stub = mission_pb2_grpc.MissionServiceStub(drone.channel)
        drone.data_stub = data_pb2_grpc.DataServiceStub(drone.channel)
        drone.connected = True
        print(f"[{drone.name}] Connected to {drone.address}")
        return True
    except Exception as e:
        print(f"[{drone.name}] Could not connect to {drone.address}: {e}")
        drone.connected = False
        return False


async def video_feed_task(drone: DroneConnection, target_fps: float = VIDEO_POLL_FPS):
    """
    Poll DataService.GetFrame for a single drone and display the decoded
    frame in a cv2 window. Runs until cancelled.
    """
    window_name = f"{drone.name} - Video Feed"
    interval = 1.0 / target_fps
    while True:
        try:
            response = await drone.data_stub.GetFrame(data_pb2.GetFrameRequest())
            encoded = response.frame.encoded_data
            if encoded:
                arr = np.frombuffer(encoded, dtype=np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if frame is not None:
                    cv2.imshow(window_name, frame)
        except grpc.aio.AioRpcError:
            # No frame published yet, or driver not ready. Keep polling.
            pass
        cv2.waitKey(1)
        await asyncio.sleep(interval)


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

    # Open a video feed window per connected drone via DataService.GetFrame
    video_tasks = [
        asyncio.create_task(video_feed_task(drone))
        for drone in manager.get_drone_list()
        if drone.connected
    ]

    try:
        await consume_keys(key_queue, tty, paused, manager)
    finally:
        stop_evt.set()
        tty.cooked()
        for task in video_tasks:
            task.cancel()
        await asyncio.gather(*video_tasks, return_exceptions=True)
        cv2.destroyAllWindows()
        # Close all channels
        for drone in manager.get_drone_list():
            if drone.channel:
                await drone.channel.close()


def load_drones_from_toml(config_path: str) -> List[Dict]:
    """
    Load drone configurations from a TOML file. Each `[[drones]]` entry needs
    a `name`, and an optional `address` (an explicit connection URI). If
    `address` is omitted, it's resolved as a locally-running vehicle name.
    """
    with open(config_path, "rb") as f:
        config = tomllib.load(f)
    drones = []
    for drone in config.get("drones", []):
        name = drone["name"]
        drones.append({"name": name, "address": resolve_address(drone.get("address", name))})
    return drones


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
        help="Drones to connect to (alternative to config file). "
             "Format: 'name=address', 'name=vehicle_name', or a bare "
             "vehicle_name/address. A value without a URI scheme is treated "
             "as the name of a locally-running vehicle and its socket "
             "address is resolved automatically. "
             "Examples: -a test-vehicle other-vehicle "
             "-a drone1=test-vehicle drone2=tcp://otherhost:50000",
    )
    args = parser.parse_args()

    # Determine drone list from config file or command line args
    drone_configs = []

    if args.config:
        # Load from TOML config file
        try:
            drone_configs = load_drones_from_toml(args.config)
            print(f"Loaded {len(drone_configs)} drone(s) from {args.config}")
        except Exception as e:
            print(f"Error loading config file {args.config}: {e}")
            sys.exit(1)
    elif args.addrs:
        # Parse from command line arguments
        for addr in args.addrs:
            if "=" in addr:
                name, target = addr.split("=", 1)
            else:
                name, target = addr, addr
            drone_configs.append({"name": name, "address": resolve_address(target)})
    else:
        # Default to the vehicle launched by `cmd/testbench/main.go`
        drone_configs.append({
            "name": DEFAULT_VEHICLE_NAME,
            "address": vehicle_socket_address(DEFAULT_VEHICLE_NAME),
        })

    # Store parsed configs in args for main()
    args.drone_configs = drone_configs

    asyncio.run(main(args))
