import asyncio
import grpc
import threading
import argparse
from pynput import keyboard

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


async def consume_keys(key_queue, vehicle, stub):
    while True:
        key = await key_queue.get()
        command = CommandRequest()
        command.vehicle_id = vehicle

        # Send RPC coro
        async def send_command(stub, command):
            try:
                async for response in stub.Command(command):
                    print(f"Response for {command.method_name}: {response.status}")
            except grpc.aio.AioRpcError as e:
                print(f"Error: {e}")

        # Joystick
        if key in ["w", "a", "s", "d", "j", "i", "k", "l"]:
            print("Sending Joystick")
            command.method_name = "Control.Joystick"
            joystick = JoystickRequest()
            match key:
                case "a":
                    joystick.velocity.y_vel = -1.0
                case "d":
                    joystick.velocity.y_vel = 1.0
                case "w":
                    joystick.velocity.x_vel = 1.0
                case "s":
                    joystick.velocity.x_vel = -1.0
                case "j":
                    joystick.velocity.angular_vel = -20.0
                case "l":
                    joystick.velocity.angular_vel = 20.0
                case "i":
                    joystick.velocity.z_vel = 1.0
                case "k":
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
        elif key == keyboard.Key.space:  # Hold
            print("Sending Hold")
            command.method_name = "Control.Hold"
            hold = HoldRequest()
            command.request.Pack(hold)
            asyncio.create_task(send_command(stub, command))
        elif key == keyboard.Key.shift_l:  # Compile Mission
            kml_path = input("Choose a KML file: ")
            dsl_path = input("Choose a DSL file: ")
            kml = open(kml_path, "rb").read()
            dsl = open(dsl_path, "r", encoding="utf-8").read()
            req = CompileMissionRequest(dsl_content=dsl)
            responses = []
            async for response in stub.CompileMission(req):
                responses.append(response)
            response = responses[-1]
            command.method_name = "Mission.Upload"
            upload = UploadRequest()
            upload.mission.content = response.compiled_dsl_content
            upload.mission.map = kml
            command.request.Pack(upload)
            asyncio.create_task(send_command(stub, command))
            while not key_queue.empty():
                key_queue.get_nowait()
                key_queue.task_done()
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
            print(f"Key not recognized: {key}")

        if key == keyboard.Key.esc:
            break

    asyncio.get_event_loop().stop()


def listen_for_keys(key_queue, loop):
    def on_press(key):
        try:
            char = key.char
        except AttributeError:
            char = key
        loop.call_soon_threadsafe(key_queue.put_nowait, char)

    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


async def main(args):
    key_queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    # Start the keyboard listener in a separate thread
    listener_thread = threading.Thread(target=listen_for_keys, args=(key_queue, loop))
    listener_thread.start()

    stub = RemoteStub(grpc.aio.insecure_channel(args.addr))

    await consume_keys(key_queue, args.vehicle, stub)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="CLI Commander", description="Gives a CLI interface to control a vehicle"
    )
    parser.add_argument("vehicle", help="name of the controlled vehicle")
    parser.add_argument(
        "-a", "--addr", default="localhost:5004", help="address of the swarm controller"
    )
    args = parser.parse_args()

    asyncio.run(main(args))
