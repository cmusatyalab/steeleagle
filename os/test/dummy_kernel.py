import os
import zmq
import time
from cnc_protocol import cnc_pb2
import asyncio
import zmq.asyncio

# Create a ZMQ context and a REQ (request) socket
context = zmq.asyncio.Context()
cmd_front_socket = context.socket(zmq.ROUTER)
cmd_front_socket.bind('tcp://' + os.environ.get('STEELEAGLE_CMD_FRONT_SOCKET_ADDR'))  # Connect to the server

# Create socket endpoints for driver
cmd_back_socket = context.socket(zmq.DEALER)
cmd_back_socket.bind('tcp://' + os.environ.get('STEELEAGLE_CMD_BACK_SOCKET_ADDR'))

msn_socket = context.socket(zmq.REQ)
msn_socket.bind('tcp://' + os.environ.get('STEELEAGLE_MSN_SOCKET_ADDR'))

class k_client():

    # Function to send a start mission command
    def send_start_mission(self):
        mission_command = cnc_pb2.Mission()
        mission_command.startMission = True
        message = mission_command.SerializeToString()
        print(f'start_mission message:{message}')
        msn_socket.send(message)
        reply = msn_socket.recv_string()
        print(f"Server reply: {reply}")

    # Function to send a stop mission command
    def send_stop_mission(self):
        mission_command = cnc_pb2.Mission()
        mission_command.stopMission = True
        message = mission_command.SerializeToString()
        msn_socket.send(message)
        reply = msn_socket.recv_string()
        print(f"Server reply: {reply}")
        
    
    async def send_takeOff(self):
        driver_command = cnc_pb2.Driver()
        driver_command.takeOff = True
        message = driver_command.SerializeToString()
        print(f"take off sent at: {time.time()}")
        await cmd_back_socket.send_multipart([message])
    
    async def proxy(self):
        print('user_driver_cmd_proxy started')
        poller = zmq.asyncio.Poller()
        poller.register(cmd_front_socket, zmq.POLLIN)
        poller.register(cmd_back_socket, zmq.POLLIN)
        
        while True:
            try:
                print("polling")
                socks = dict(await poller.poll())

                # Check for messages on the ROUTER socket
                if cmd_front_socket in socks:
                    print("Proxy: Message received at ROUTER (Frontend)")
                    message_parts = await cmd_front_socket.recv_multipart()
                    identity = message_parts[0]
                    msg = message_parts[1]
                    print(f"Proxy: Received message from commander, identity: {identity}, message: {msg}")

                    # Forward message to backend
                    await cmd_back_socket.send_multipart([identity, msg])

                # Check for messages on the DEALER socket
                if cmd_back_socket in socks:
                    print("Proxy: Message received at DEALER (Backend)")
                    message_parts = await cmd_back_socket.recv_multipart()
                    identity = message_parts[0]
                    msg = message_parts[1]
                    print(f"Proxy: Forwarding message back to commander, identity: {identity}, message: {msg}")
                    await cmd_front_socket.send_multipart([identity, msg])

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