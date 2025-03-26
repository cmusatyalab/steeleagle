import os
import zmq
import time
from cnc_protocol import cnc_pb2
import asyncio
import zmq.asyncio
from util.utils import SocketOperation, setup_socket
import logging 
import sys

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Setting up sockets
# context = zmq.asyncio.Context()
# tel_sock = context.socket(zmq.SUB)
# cam_sock = context.socket(zmq.SUB)
# cmd_front_sock = context.socket(zmq.ROUTER)
# cmd_back_sock = context.socket(zmq.DEALER)
# msn_sock = context.socket(zmq.REQ)
# tel_sock.setsockopt(zmq.SUBSCRIBE, b'') # Subscribe to all topics
# tel_sock.setsockopt(zmq.CONFLATE, 1)
# cam_sock.setsockopt(zmq.SUBSCRIBE, b'')  # Subscribe to all topics
# cam_sock.setsockopt(zmq.CONFLATE, 1)
# setup_socket(tel_sock, 'bind', 'TEL_PORT', 'Created telemetry socket endpoint')
# setup_socket(cam_sock, 'bind', 'CAM_PORT', 'Created camera socket endpoint')
# setup_socket(cmd_front_sock, 'bind', 'CMD_FRONT_PORT', 'Created command frontend socket endpoint')
# setup_socket(cmd_back_sock, 'bind', 'CMD_BACK_PORT', 'Created command backend socket endpoint')
# setup_socket(msn_sock, 'bind', 'MSN_PORT', 'Created user space mission control socket endpoint')
# Setting up conetxt
context = zmq.asyncio.Context()

drone_id = os.environ.get('DRONE_ID')
# Setting up sockets
cmd_front_cmdr_sock = context.socket(zmq.DEALER)
cmd_front_cmdr_sock.setsockopt(zmq.IDENTITY, drone_id.encode('utf-8'))
cmd_front_usr_sock = context.socket(zmq.DEALER)
cmd_back_sock = context.socket(zmq.DEALER)
msn_sock = context.socket(zmq.REQ)
setup_socket(cmd_front_cmdr_sock, SocketOperation.CONNECT, 'CMD_FRONT_CMDR_PORT', 'Connected command frontend cmdr socket endpoint', os.environ.get('STEELEAGLE_GABRIEL_SERVER'))
setup_socket(cmd_front_usr_sock, SocketOperation.BIND, 'CMD_FRONT_USR_PORT', 'Created command frontend user socket endpoint')
setup_socket(cmd_back_sock, SocketOperation.BIND, 'CMD_BACK_PORT', 'Created command backend socket endpoint')
setup_socket(msn_sock, SocketOperation.BIND, 'MSN_PORT', 'Created userspace mission control socket endpoint')


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
        poller.register(cmd_front_cmdr_sock, zmq.POLLIN)
        poller.register(cmd_back_sock, zmq.POLLIN)
        
        while True:
            try:
                print("polling")
                socks = dict(await poller.poll())

                # Check for messages on the ROUTER socket
                if cmd_front_cmdr_sock in socks:
                    message = await cmd_front_cmdr_sock.recv_multipart()
                    print(f"proxy : 1 Received message from BACKEND: {message}")

                    # Filter the message
                    identity = message[0]
                    cmd = message[1]
                    print(f"proxy : 2 Received message from BACKEND: identity: {identity}")
                    
                    if identity == b'cmdr':
                        await self.send_takeOff()
                    elif identity == b'usr':
                        await cmd_back_sock.send_multipart(message)
                    else:
                        print(f"cmd_proxy: invalid identity")


                # Check for messages on the DEALER socket
                if cmd_back_sock in socks:
                    message = await cmd_back_sock.recv_multipart()
                    print(f"proxy : 3 Received message from FRONTEND: {message}")

                    # Filter the message
                    identity = message[0]
                    cmd = message[1]
                    print(f"proxy : 4 Received message from FRONTEND: identity: {identity}")
                    
                    if identity == b'cmdr':
                        print(f"proxy : 5 Received message from FRONTEND: discard bc of cmdr")
                        pass
                    elif identity == b'usr':
                        print(f"proxy : 5 Received message from FRONTEND: sent back bc of user")
                        await cmd_front_cmdr_sock.send_multipart(message)
                    else:
                        print(f"cmd_proxy: invalid identity")
                        
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