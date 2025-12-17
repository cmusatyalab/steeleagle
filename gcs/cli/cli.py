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
from steeleagle_sdk.protocol.services.remote_service_pb2_grpc import RemoteStub
from steeleagle_sdk.protocol.services.remote_service_pb2 import (
    CommandRequest,
    CompileMissionRequest,
)
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
async def consume_keys(key_queue, vehicle, stub, tty: TTYMode, paused: threading.Event):
    print(
        "Controls: w/a/s/d (XY), i/k (Z), j/l (yaw), t=TakeOff, g=Land, ' ' (Hold), m=Start, n=Stop, c=Compile+Upload, Esc to quit"
    )

    while True:
        key = await key_queue.get()
        command = CommandRequest()
        command.vehicle_id = vehicle

        async def send_command(stub, command):
            try:
                async for response in stub.Command(command):
                    print(f"Response for {command.method_name}: {response.status}")
            except grpc.aio.AioRpcError as e:
                print(f"Error: {e}")

        # Quit on ESC
        if key == "\x1b":  # ESC
            break

        # Joystick
        if key in ["w", "a", "s", "d", "j", "i", "k", "l"]:
            print("Sending Joystick")
            command.method_name = "Control.Joystick"
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
            command.request.Pack(joystick)
            asyncio.create_task(send_command(stub, command))

        elif key == "t":  # TakeOff
            print("Sending TakeOff")
            command.method_name = "Control.TakeOff"
            takeoff = TakeOffRequest()
            takeoff.take_off_altitude = 10.0
            command.request.Pack(takeoff)
            asyncio.create_task(send_command(stub, command))

        elif key == "g":  # Land
            print("Sending Land")
            command.method_name = "Control.Land"
            land = LandRequest()
            command.request.Pack(land)
            asyncio.create_task(send_command(stub, command))

        elif key == " ":  # Hold (space)
            print("Sending Hold")
            command.method_name = "Control.Hold"
            hold = HoldRequest()
            command.request.Pack(hold)
            asyncio.create_task(send_command(stub, command))

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
                    req = CompileMissionRequest(dsl_content=dsl)
                    responses = []
                    try:
                        async for response in stub.CompileMission(req):
                            responses.append(response)
                    except grpc.aio.AioRpcError as e:
                        print(f"[Compile] RPC error: {e}")
                        responses = []

                    if not responses:
                        print("[Compile] No responses.")
                    else:
                        response = responses[-1]
                        command.method_name = "Mission.Upload"
                        upload = UploadRequest()
                        upload.mission.content = response.compiled_dsl_content
                        upload.mission.map = kml
                        command.request.Pack(upload)
                        asyncio.create_task(send_command(stub, command))
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
            command.method_name = "Mission.Start"
            start = StartRequest()
            command.request.Pack(start)
            asyncio.create_task(send_command(stub, command))

        elif key == "n":  # Stop Mission
            command.method_name = "Mission.Stop"
            stop = StopRequest()
            command.request.Pack(stop)
            asyncio.create_task(send_command(stub, command))

        else:
            if key not in ("\n", "\r"):
                print(f"Key not recognized: {repr(key)}")

    # exit
    asyncio.get_event_loop().stop()


async def main(args):
    key_queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    # gRPC channel (wait until ready so first key doesn't race)
    channel = grpc.aio.insecure_channel(args.addr)
    try:
        await asyncio.wait_for(channel.channel_ready(), timeout=5.0)
    except Exception as e:
        print(f"Could not connect to gRPC at {args.addr}: {e}")
        return
    stub = RemoteStub(channel)

    # Raw TTY + reader thread
    tty = TTYMode()
    tty.raw()

    paused = threading.Event()
    stop_evt = threading.Event()
    listener_thread = threading.Thread(
        target=listen_for_keys, args=(key_queue, loop, paused, stop_evt), daemon=True
    )
    listener_thread.start()

    try:
        await consume_keys(key_queue, args.vehicle, stub, tty, paused)
    finally:
        stop_evt.set()
        tty.cooked()
        await channel.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="CLI Commander",
        description="Gives a CLI interface to control a vehicle (WSL-friendly)",
    )
    parser.add_argument("vehicle", help="name of the controlled vehicle")
    parser.add_argument(
        "-a", "--addr", default="localhost:5004", help="address of the swarm controller"
    )
    args = parser.parse_args()

    asyncio.run(main(args))
