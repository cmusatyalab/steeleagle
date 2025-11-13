#!/usr/bin/env python3
import asyncio
import grpc
import threading
import os
import sys
import select
import contextlib

# Protocol imports
from steeleagle_sdk.protocol.services.mission_service_pb2_grpc import MissionStub
from steeleagle_sdk.protocol.services.control_service_pb2_grpc import ControlStub
from steeleagle_sdk.protocol.services.control_service_pb2 import JoystickRequest, TakeOffRequest, LandRequest, HoldRequest
from steeleagle_sdk.protocol.services.mission_service_pb2 import UploadRequest, StartRequest, StopRequest


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


def listen_for_keys(key_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop,
                    paused: threading.Event, stop_evt: threading.Event):
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
            ch = os.read(fd, 1).decode(errors='ignore')
        except Exception:
            ch = ''
        if ch:
            loop.call_soon_threadsafe(key_queue.put_nowait, ch)


# --------- main consumer ---------
async def consume_keys(key_queue, driver_stub: ControlStub, msn_stub: MissionStub, tty: TTYMode, paused: threading.Event):
    print("Controls: w/a/s/d (XY), i/k (Z), j/l (yaw), t=TakeOff, g=Land, ' ' (Hold), m=Start, n=Stop, u=Upload, Esc to quit")

    while True:
        key = await key_queue.get()

        # Quit on ESCd = "steeleagle_sdk
        if key == '\x1b':  # ESC
            break

        # Joystick
        if key in ['w', 'a', 's', 'd', 'j', 'i', 'k', 'l']:
            print('Sending Joystick')
            joystick = JoystickRequest()
            if   key == 'a': joystick.velocity.y_vel = -1.0
            elif key == 'd': joystick.velocity.y_vel =  1.0
            elif key == 'w': joystick.velocity.x_vel =  1.0
            elif key == 's': joystick.velocity.x_vel = -1.0
            elif key == 'j': joystick.velocity.angular_vel = -20.0
            elif key == 'l': joystick.velocity.angular_vel =  20.0
            elif key == 'i': joystick.velocity.z_vel =  1.0
            elif key == 'k': joystick.velocity.z_vel = -1.0
            asyncio.create_task(driver_stub.Joystick(joystick))

        elif key == 't':  # TakeOff
            print('Sending TakeOff')
            takeoff = TakeOffRequest()
            takeoff.take_off_altitude = 10.0
            asyncio.create_task(driver_stub.TakeOff(takeoff))

        elif key == 'g':  # Land
            print('Sending Land')
            land = LandRequest()
            asyncio.create_task(driver_stub.Land(land))

        elif key == ' ':  # Hold (space)
            print('Sending Hold')
            hold = HoldRequest()
            asyncio.create_task(driver_stub.Hold(hold))

        elif key == 'u':
            paused.set()
            tty.cooked()
            try:
                kml_path = input('Choose a KML file: ').strip()
                compiled_msn_path = input('Choose a compiled mission JSON file: ').strip()

                try:
                    kml = open(kml_path, "rb").read()
                except Exception as e:
                    print(f"[Upload] Failed to read KML: {e}")
                    kml = None
                try:
                    compiled_msn = open(compiled_msn_path, "r", encoding="utf-8").read()
                except Exception as e:
                    print(f"[Upload] Failed to read mission: {e}")
                    compiled_msn = None

                if kml is None or compiled_msn is None:
                    pass
                else:
                    print("[Upload] Uploading Mission…")
                    upload = UploadRequest()
                    upload.mission.content = compiled_msn
                    upload.mission.map = kml
                    asyncio.create_task(msn_stub.Upload(upload))
            finally:
                # Drain any buffered keys typed during prompts
                while not key_queue.empty():
                    with contextlib.suppress(Exception):
                        key_queue.get_nowait()
                        key_queue.task_done()
                # Back to raw mode + resume reader
                tty.raw()
                paused.clear()

        elif key == 'm':  # Start Mission
            start = StartRequest()
            asyncio.create_task(msn_stub.Start(start))

        elif key == 'n':  # Stop Mission
            stop = StopRequest()
            asyncio.create_task(msn_stub.Stop(stop))

        else:
            if key not in ('\n', '\r'):
                print(f'Key not recognized: {repr(key)}')

    # exit
    asyncio.get_event_loop().stop()


async def async_main():
    key_queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    driver_channel = grpc.aio.insecure_channel('unix:///tmp/driver.sock')
    msn_channel = grpc.aio.insecure_channel('unix:///tmp/mission.sock')
    try:
        await asyncio.wait_for(driver_channel.channel_ready(), timeout=5.0)
        await asyncio.wait_for(msn_channel.channel_ready(), timeout=5.0)
    except Exception as e:
        print(f"Could not connect to gRPC{e}")
        return
    
    driver_stub = ControlStub(driver_channel)
    msn_stub = MissionStub(msn_channel)

    # Raw TTY + reader thread
    tty = TTYMode()
    tty.raw()

    paused = threading.Event()
    stop_evt = threading.Event()
    listener_thread = threading.Thread(
        target=listen_for_keys,
        args=(key_queue, loop, paused, stop_evt),
        daemon=True
    )
    listener_thread.start()

    try:
        await consume_keys(key_queue, driver_stub, msn_stub, tty, paused)
    finally:
        stop_evt.set()
        tty.cooked()
        await driver_channel.close()
        await msn_channel.close()

def main():
    asyncio.run(async_main())
    
if __name__ == "__main__":
    asyncio.run(async_main())
