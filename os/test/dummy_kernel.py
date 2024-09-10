import os
import zmq
import time
from cnc_protocol import cnc_pb2
import asyncio
import zmq.asyncio
from util.utils import setup_socket

# Setting up sockets
context = zmq.asyncio.Context()
tel_sock = context.socket(zmq.SUB)
cam_sock = context.socket(zmq.SUB)
cmd_front_sock = context.socket(zmq.ROUTER)
cmd_back_sock = context.socket(zmq.DEALER)
msn_sock = context.socket(zmq.REQ)
tel_sock.setsockopt(zmq.SUBSCRIBE, b'') # Subscribe to all topics
tel_sock.setsockopt(zmq.CONFLATE, 1)
cam_sock.setsockopt(zmq.SUBSCRIBE, b'')  # Subscribe to all topics
cam_sock.setsockopt(zmq.CONFLATE, 1)
setup_socket(tel_sock, 'bind', 'TEL_PORT', 'Created telemetry socket endpoint')
setup_socket(cam_sock, 'bind', 'CAM_PORT', 'Created camera socket endpoint')
setup_socket(cmd_front_sock, 'bind', 'CMD_FRONT_PORT', 'Created command frontend socket endpoint')
setup_socket(cmd_back_sock, 'bind', 'CMD_BACK_PORT', 'Created command backend socket endpoint')
setup_socket(msn_sock, 'bind', 'MSN_PORT', 'Created user space mission control socket endpoint')

# # Create a ZMQ context and a REQ (request) socket
# context = zmq.asyncio.Context()
# cmd_front_sock = context.socket(zmq.ROUTER)
# cmd_front_sock.bind('tcp://' + os.environ.get('STEELEAGLE_cmd_front_sock_ADDR'))  # Connect to the server

# # Create socket endpoints for driver
# cmd_back_sock = context.socket(zmq.DEALER)
# cmd_back_sock.bind('tcp://' + os.environ.get('STEELEAGLE_cmd_back_sock_ADDR'))

# msn_sock = context.socket(zmq.REQ)
# msn_sock.bind('tcp://' + os.environ.get('STEELEAGLE_msn_sock_ADDR'))

class k_client():

    # Function to send a start mission command
    def send_start_mission(self):
        mission_command = cnc_pb2.Mission()
        mission_command.startMission = True
        message = mission_command.SerializeToString()
        print(f'start_mission message:{message}')
        msn_sock.send(message)
        reply = msn_sock.recv_string()
        print(f"Server reply: {reply}")

    # Function to send a stop mission command
    def send_stop_mission(self):
        mission_command = cnc_pb2.Mission()
        mission_command.stopMission = True
        message = mission_command.SerializeToString()
        msn_sock.send(message)
        reply = msn_sock.recv_string()
        print(f"Server reply: {reply}")
        
    
    async def send_takeOff(self):
        driver_command = cnc_pb2.Driver()
        driver_command.takeOff = True
        message = driver_command.SerializeToString()
        print(f"take off sent at: {time.time()}")
        await cmd_back_sock.send_multipart([message])
    
    async def proxy(self):
        print('user_driver_cmd_proxy started')
        poller = zmq.asyncio.Poller()
        poller.register(cmd_front_sock, zmq.POLLIN)
        poller.register(cmd_back_sock, zmq.POLLIN)
        
        while True:
            try:
                print("polling")
                socks = dict(await poller.poll())

                # Check for messages on the ROUTER socket
                if cmd_front_sock in socks:
                    print("Proxy: Message received at ROUTER (Frontend)")
                    message_parts = await cmd_front_sock.recv_multipart()
                    identity = message_parts[0]
                    msg = message_parts[1]
                    print(f"Proxy: Received message from commander, identity: {identity}, message: {msg}")

                    # Forward message to backend
                    await cmd_back_sock.send_multipart([identity, msg])

                # Check for messages on the DEALER socket
                if cmd_back_sock in socks:
                    print("Proxy: Message received at DEALER (Backend)")
                    message_parts = await cmd_back_sock.recv_multipart()
                    identity = message_parts[0]
                    msg = message_parts[1]
                    print(f"Proxy: Forwarding message back to commander, identity: {identity}, message: {msg}")
                    await cmd_front_sock.send_multipart([identity, msg])

            except Exception as e:
                print(f"Proxy error: {e}")

    async def a_run(self):
        # Interactive command input loop
        asyncio.create_task(self.proxy())
        
        while True:
            await asyncio.sleep(0)

if __name__ == "__main__":
    print("Starting client")
    k = k_client()
    asyncio.run(k.a_run())