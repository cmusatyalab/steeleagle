#!/usr/bin/env python3
import asyncio
import grpc
import threading
import argparse
import os
import sys
import select
import contextlib

# Protocol imports
from steeleagle_sdk.protocol.services.control_service_pb2 import (
    JoystickRequest,
    TakeOffRequest,
    LandRequest,
    HoldRequest,
)
from steeleagle_sdk.protocol.services.mission_service_pb2 import (
    UploadRequest,
    StartRequest,
    StopRequest,
)
from steeleagle_sdk.protocol.services.control_service_pb2_grpc import ControlStub
from steeleagle_sdk.protocol.services.mission_service_pb2_grpc import MissionStub
from steeleagle_sdk.dsl import build_mission

IDENTITY_MD = (("identity", "server"),)

# --------- raw TTY helpers (WSL-friendly) ---------
class TTYMode:
    def __init__(self):
        self.fd = sys.stdin.fileno()
        self._orig = None
        self._supported = sys.stdin.isatty()

    def raw(self):
        if not self._supported:
            return
        import termios, tty
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


# --------- main consumer ---------
async def consume_keys(
    key_queue: asyncio.Queue,
    tty: TTYMode,
    paused: threading.Event,
    cstub: ControlStub,
    mstub: MissionStub,
):
    print(
        "Controls: w/a/s/d (XY), i/k (Z), j/l (yaw), t=TakeOff, g=Land, "
        "' ' (Hold), m=Start, n=Stop, c=Compile+Upload, Esc to quit"
    )

    while True:
        key = await key_queue.get()

        # Quit on ESC
        if key == "\x1b":  # ESC
            break

        async def _send_stream(call, command_name: str):
            try:
                # For server-streaming RPCs
                async for response in call:
                    print(f"Response for {command_name}: {response.status}")
            except grpc.aio.AioRpcError as e:
                print(f"Error during {command_name}: {e}")
        
        async def _send_unary(call, command_name: str):
                try:
                    # assuming unary RPC that just acks
                    await call
                except grpc.aio.AioRpcError as e:
                    print(f"Error during {command_name}: {e}")
        # Joystick
        if key in ["w", "a", "s", "d", "j", "i", "k", "l"]:
            print("Sending Joystick")
            joystick = JoystickRequest()
            if key == "a":
                joystick.velocity.y_vel = -1.0
            elif key == "d":
                joystick.velocity.y_vel = 1.0
            elif key == "w":
                joystick.velocity.x_vel = 1.0
            elif key == "s":
                joystick.velocity.x_vel = -1.0
            elif key == "j":
                joystick.velocity.angular_vel = -20.0
            elif key == "l":
                joystick.velocity.angular_vel = 20.0
            elif key == "i":
                joystick.velocity.z_vel = 1.0
            elif key == "k":
                joystick.velocity.z_vel = -1.0

            call = cstub.Joystick(joystick, metadata=IDENTITY_MD)
            asyncio.create_task(_send_unary(call, "joystick"))

        elif key == "t":  # TakeOff
            print("Sending TakeOff")
            takeoff = TakeOffRequest()
            takeoff.take_off_altitude = 10.0
            call = cstub.TakeOff(takeoff, metadata=IDENTITY_MD)
            asyncio.create_task(_send_stream(call, "takeoff"))

        elif key == "g":  # Land
            print("Sending Land")
            land = LandRequest()
            call = cstub.Land(land, metadata=IDENTITY_MD)
            asyncio.create_task(_send_stream(call, "land"))

        elif key == " ":  # Hold (space)
            print("Sending Hold")
            hold = HoldRequest()
            call = cstub.Hold(hold, metadata=IDENTITY_MD)
            asyncio.create_task(_send_stream(call, "hold"))

        elif key == "c":  # Compile Mission (use input() in cooked mode)
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
                    dsl = open(dsl_path, "r", encoding="utf-8").read()
                except Exception as e:
                    print(f"[Compile] Failed to read DSL: {e}")
                    dsl = None

                if kml is None or dsl is None:
                    pass
                else:
                    print("[Compile] Compiling DSL…")
                    mission_json = build_mission(dsl)
                    if not mission_json:
                        print("[Compile] No responses.")
                    else:
                        upload = UploadRequest()
                        upload.mission.content = mission_json
                        upload.mission.map = kml
                        # Assuming Upload is unary or server-streaming:
                        call = mstub.Upload(upload, metadata=IDENTITY_MD)
                        asyncio.create_task(_send_stream(call, "upload"))
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
            print("Sending Start")
            start = StartRequest()
            call = mstub.Start(start, metadata=IDENTITY_MD)
            asyncio.create_task(_send_stream(call, "start"))

        elif key == "n":  # Stop Mission
            print("Sending Stop")
            stop = StopRequest()
            call = mstub.Stop(stop, metadata=IDENTITY_MD)
            asyncio.create_task(_send_stream(call, "stop"))

        else:
            if key not in ("\n", "\r"):
                print(f"Key not recognized: {repr(key)}")


async def main(args):
    key_queue: asyncio.Queue[str] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    tty = TTYMode()
    tty.raw()

    paused = threading.Event()
    stop_evt = threading.Event()

    # Create channel & stubs *inside* the running loop
    async with grpc.aio.insecure_channel(args.addr) as channel:
        try:
            await asyncio.wait_for(channel.channel_ready(), timeout=5.0)
        except Exception as e:
            print(f"Could not connect to gRPC at {args.addr}: {e}")
            tty.cooked()
            return

        cstub = ControlStub(channel)
        mstub = MissionStub(channel)

        listener_thread = threading.Thread(
            target=listen_for_keys,
            args=(key_queue, loop, paused, stop_evt),
            daemon=True,
        )
        listener_thread.start()

        try:
            await consume_keys(key_queue, tty, paused, cstub, mstub)
        finally:
            stop_evt.set()
            tty.cooked()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="CLI Commander",
        description="Gives a CLI interface to control a vehicle (WSL-friendly)",
    )
    parser.add_argument(
        "-a",
        "--addr",
        default="unix:///tmp/kernel.sock",
        help="address of the kernel service",
    )
    args = parser.parse_args()

    asyncio.run(main(args))
