import asyncio
import logging
import sys

import zmq
from cnc_protocol import cnc_pb2
from util.utils import SocketOperation, setup_socket

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

context = zmq.asyncio.Context()

msn_sock = context.socket(zmq.REQ)
setup_socket(msn_sock, SocketOperation.BIND, 'MSN_PORT', 'Created userspace mission control socket endpoint')

class c_client:
    
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
        
    async def a_run(self):
        # Interactive command input loop
        MCOM_SET = ['start', 'stop']
        while True:
            user_input = input()
 
            if user_input == 'start':
                self.send_start_mission()
            elif user_input == 'stop':
                self.send_stop_mission()
            else:
                print("Invalid command.")
                
            await asyncio.sleep(0)

if __name__ == "__main__":
    print("Starting client")
    k = c_client()
    asyncio.run(k.a_run())
