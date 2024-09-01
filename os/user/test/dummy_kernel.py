import os
import zmq
import time
from cnc_protocol import cnc_pb2
import asyncio

# Create a ZMQ context and a REQ (request) socket
context = zmq.Context()
socket = context.socket(zmq.REQ)
socket.bind('tcp://' + os.environ.get('STEELEAGLE_KERNEL_COMMAND_ADDR'))  # Connect to the server

# Create socket endpoints for driver
driver_socket = context.socket(zmq.DEALER)
addr = 'tcp://' + os.environ.get('STEELEAGLE_DRIVER_COMMAND_ADDR')
driver_socket.connect(addr)

class k_client():

    # Function to send a start mission command
    def send_start_mission(self):
        mission_command = cnc_pb2.Mission()
        mission_command.startMission = True
        message = mission_command.SerializeToString()
        print(f'start_mission message:{message}')
        socket.send(message)
        reply = socket.recv_string()
        print(f"Server reply: {reply}")

    # Function to send a stop mission command
    def send_stop_mission(self):
        mission_command = cnc_pb2.Mission()
        mission_command.stopMission = True
        message = mission_command.SerializeToString()
        socket.send(message)
        reply = socket.recv_string()
        print(f"Server reply: {reply}")
        
    
    def send_takeOff(self):
        driver_command = cnc_pb2.Driver()
        driver_command.takeOff = True
        message = driver_command.SerializeToString()
        print(f"take off sent at: {time.time()}")
        driver_socket.send_multipart([message])

    async def a_run(self):
        # Interactive command input loop
        while True:
            user_input = input("Enter 'start' to start the mission or 'stop' to stop the mission (type 'exit' to quit): ").strip().lower()
            if user_input == 'start':
                self.send_start_mission()
            elif user_input == 'stop':
                self.send_stop_mission()
            elif user_input == 'takeoff':
                self.send_takeOff()
            elif user_input == "exit":
                print("Exiting client.")
                break
            else:
                print("Invalid command.")

if __name__ == "__main__":
    print("Starting client")
    k = k_client()
    asyncio.run(k.a_run())