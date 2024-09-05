import os
import zmq
import time
from cnc_protocol import cnc_pb2
import asyncio
import zmq.asyncio


context = zmq.asyncio.Context()

# Create socket endpoints for driver
cmd_front_socket = context.socket(zmq.DEALER)
cmd_front_socket.connect('tcp://' + os.environ.get('STEELEAGLE_CMD_FRONT_SOCKET_ADDR'))



class c_client():
    async def send_takeOff(self):
        driver_command = cnc_pb2.Driver()
        driver_command.takeOff = True
        message = driver_command.SerializeToString()
        await cmd_front_socket.send_multipart([message])
        print(f"commander: take off sent at: {time.time()}")
        
    async def a_run(self):
        # Interactive command input loop
        
        while True:
            user_input = input("Enter 'takeoff' to send the take off cmd: ").strip().lower()
 
            if user_input == 'takeoff':
                asyncio.create_task(self.send_takeOff())
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