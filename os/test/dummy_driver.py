import asyncio
import os
import time

import zmq
import zmq.asyncio
from cnc_protocol import cnc_pb2
from util.utils import setup_socket

context = zmq.asyncio.Context()
cmd_back_sock = context.socket(zmq.DEALER)
tel_sock = context.socket(zmq.PUB)
cam_sock = context.socket(zmq.PUB)
tel_sock.setsockopt(zmq.CONFLATE, 1)
cam_sock.setsockopt(zmq.CONFLATE, 1)
setup_socket(tel_sock, 'connect', 'TEL_PORT', 'Created telemetry socket endpoint', os.environ.get("LOCALHOST"))
setup_socket(cam_sock, 'connect', 'CAM_PORT', 'Created camera socket endpoint', os.environ.get("LOCALHOST"))
setup_socket(cmd_back_sock, 'connect', 'CMD_BACK_PORT', 'Created command backend socket endpoint', os.environ.get("LOCALHOST"))




async def camera_stream(drone, camera_sock):
    frame_id = 0
    cam_message = cnc_pb2.Frame() 
    # while drone.isConnected():
    while True:
        try:
            x = 1
        except Exception as e:
            pass
        await asyncio.sleep(0.033)

async def telemetry_stream(drone, telemetry_sock):
    tel_message = cnc_pb2.Telemetry()
    # while drone.isConnected():
    while True:
        try:
            x = 2
        except Exception as e:
            print(f'Failed to get telemetry, error: {e}')
        await asyncio.sleep(0)
        
class d_server():

    async def a_run(self):
        asyncio.create_task(telemetry_stream(None, tel_sock))
        asyncio.create_task(camera_stream(None, cam_sock))    
        while True:
            try:
                # Receive a message from the DEALER socket
                message_parts = await cmd_back_sock.recv_multipart()
                
                # Expecting three parts: [identity, empty, message]
                if len(message_parts) != 2:
                    print(f"Invalid message received: {message_parts}")
                    continue
                
                identity = message_parts[0]  # Identity of the DEALER socket
                message = message_parts[1]     # The empty delimiter part
                # message = message_parts[2]   # The actual serialized request
                
                # Print each part to understand the structure
                print(f"Identity: {identity}")
                # print(f"Empty delimiter: {empty}")
                print(f"Message: {message}")
                
                # Parse the message
                driver_req = cnc_pb2.Driver()
                driver_req.ParseFromString(message)
                print(f"Received the message: {driver_req}")
                print(f"Request seqNum: {driver_req.seqNum}")
                
                # Print parsed message and determine the response
                if driver_req.takeOff:
                    print(f"take off received: {time.time()}")
                    print("Request: take Off")
                    driver_req.resp = cnc_pb2.ResponseStatus.COMPLETED
                else:
                    print("Unknown request")
                    driver_req.resp = cnc_pb2.ResponseStatus.NOTSUPPORTED
                
                serialized_response = driver_req.SerializeToString()
                
                # Send a reply back to the client with the identity frame and empty delimiter
                cmd_back_sock.send_multipart([identity, serialized_response])
                
                print(f"done processing request")
            except Exception as e:
                print(f"error: {e}")
                
if __name__ == "__main__":
    print("Starting server")
    d= d_server()
    asyncio.run(d.a_run())