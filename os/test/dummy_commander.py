import os
import zmq
import time
from cnc_protocol import cnc_pb2
import asyncio
import zmq.asyncio


context = zmq.Context()

# Create socket endpoints for driver
cmd_front_socket = context.socket(zmq.DEALER)
kernel_sock_identity = b'cmdr'
cmd_front_socket.setsockopt(zmq.IDENTITY, kernel_sock_identity)
cmd_front_socket.connect('tcp://' + os.environ.get('TEST_SOCK_ADDR'))



class c_client():
    def send_takeOff(self):
        driver_command = cnc_pb2.Extras()
        driver_command.cmd.takeoff = True
        message = driver_command.SerializeToString()
        cmd_front_socket.send_multipart([message])
        print(f"commander: take off sent at: {time.time()}")
        
    def send_startM(self):
        driver_command = cnc_pb2.Extras()
        driver_command.cmd.script_url = "https://www.ant.com"
        message = driver_command.SerializeToString()
        cmd_front_socket.send_multipart([message])
        print(f"commander: mission sent at: {time.time()}")
        
    async def a_run(self):
        # Interactive command input loop
        
        while True:
            user_input = input("Enter 'takeoff' to send the take off cmd: ").strip().lower()
 
            if user_input == 'takeoff':
                self.send_takeOff()
            elif user_input == 'start':
                self.send_startM()
            elif user_input == "exit":
                print("Exiting client.")
                break
            else:
                print("Invalid command.")
                
            await asyncio.sleep(0)

if __name__ == "__main__":
    print("Starting client")
    k = c_client()
    asyncio.run(k.a_run())