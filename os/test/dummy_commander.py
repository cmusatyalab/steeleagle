import asyncio
import os
import time

import zmq
import zmq.asyncio
from cnc_protocol import cnc_pb2
from util.utils import setup_socket

context = zmq.Context()

# Create socket endpoints for driver
cmd_front_sock = context.socket(zmq.DEALER)
cmdr_identity = b"cmdr"
cmd_front_sock.setsockopt(zmq.IDENTITY, cmdr_identity)
setup_socket(
    cmd_front_sock,
    "connect",
    "CMD_FRONT_PORT",
    "Created command frontend socket endpoint",
    os.environ.get("LOCALHOST"),
)


class c_client:
    def send_takeOff(self):
        driver_command = cnc_pb2.Extras()
        driver_command.cmd.takeoff = True
        message = driver_command.SerializeToString()
        cmd_front_sock.send_multipart([message])
        print(f"commander: take off sent at: {time.time()}")

    def send_land(self):
        driver_command = cnc_pb2.Extras()
        driver_command.cmd.land = True
        message = driver_command.SerializeToString()
        cmd_front_sock.send_multipart([message])
        print(f"commander: land sent at: {time.time()}")

    def send_MCOM(self, key):
        driver_command = cnc_pb2.Extras()
        match key:
            case "w":
                driver_command.cmd.pcmd.pitch = 25
            case "s":
                driver_command.cmd.pcmd.pitch = -25
            case "a":
                driver_command.cmd.pcmd.roll = 25
            case "d":
                driver_command.cmd.pcmd.roll = -25
            case "f":
                pass
        message = driver_command.SerializeToString()
        cmd_front_sock.send_multipart([message])
        print(f"commander: manual command of '{key}' sent at: {time.time()}")

    def send_startM(self):
        driver_command = cnc_pb2.Extras()
        driver_command.cmd.script_url = "https://www.ant.com"
        message = driver_command.SerializeToString()
        cmd_front_sock.send_multipart([message])
        print(f"commander: mission sent at: {time.time()}")

    async def a_run(self):
        # Interactive command input loop
        MCOM_SET = ["w", "a", "s", "d", "i", "j", "k", "l", "f"]
        while True:
            user_input = input()

            if user_input == "t":
                self.send_takeOff()
            elif user_input == "g":
                self.send_land()
            elif user_input == "m":
                self.send_startM()
            elif user_input in MCOM_SET:
                self.send_MCOM(user_input)
            elif user_input == "x":
                print("Exiting client.")
                break
            else:
                print("Invalid command.")

            await asyncio.sleep(0)


if __name__ == "__main__":
    print("Starting client")
    k = c_client()
    asyncio.run(k.a_run())
