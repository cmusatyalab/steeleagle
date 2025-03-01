import asyncio
import os

import zmq
from cnc_protocol import cnc_pb2

# Create a pub/sub socket that telemetry can be read from
context = zmq.Context()
telemetry_socket = context.socket(zmq.SUB)
telemetry_socket.setsockopt(zmq.SUBSCRIBE, b"")
addr = "tcp://" + os.environ.get("STEELEAGLE_DRIVER_TEL_SUB_ADDR")
print(f"Telemetry address: {addr}")
if addr:
    telemetry_socket.connect(addr)
    print("Connected to telemetry publish endpoint")
else:
    print("Cannot get telemetry publish endpoint from system")
    quit()


class Dummy:
    def __init__(self):
        self.telemetry_socket = telemetry_socket
        self.telemetry_cache = {
            "location": {"latitude": None, "longitude": None, "altitude": None},
            "battery": None,
            "magnetometer": None,
            "bearing": None,
        }

    async def telemetry_handler(self):
        print("Telemetry handler started")

        while True:
            try:
                print("Telemetry Handler: Waiting for telemetry")
                msg = self.telemetry_socket.recv(flags=zmq.NOBLOCK)
                print("Telemetry Handler: Received telemetry")
                telemetry = cnc_pb2.Telemetry()
                telemetry.ParseFromString(msg)
                print(f"Telemetry Handler: {telemetry}")
                self.telemetry_cache["location"]["latitude"] = telemetry.global_position.latitude
                self.telemetry_cache["location"]["longitude"] = telemetry.global_position.longitude
                self.telemetry_cache["location"]["altitude"] = telemetry.global_position.altitude
                self.telemetry_cache["battery"] = telemetry.battery
                self.telemetry_cache["magnetometer"] = telemetry.mag
                self.telemetry_cache["bearing"] = telemetry.drone_attitude.yaw

                print(
                    f"Telemetry Handler: Latitude: {telemetry.global_position.latitude} Longitude: {telemetry.global_position.longitude} Altitude: {telemetry.global_position.altitude}"
                )
                print(f"Telemetry Handler: Battery: {telemetry.battery}")
                print(f"Telemetry Handler: Magnetometer: {telemetry.mag}")
                print(f"Telemetry Handler: Bearing: {telemetry.drone_attitude.yaw}")
            except zmq.Again:
                print("Telemetry handler no received telemetry")
                pass

            except Exception as e:
                print(f"Telemetry Handler Exception: {e}")

            await asyncio.sleep(0)


if __name__ == "__main__":
    k = Dummy()
    asyncio.run(k.telemetry_handler())
