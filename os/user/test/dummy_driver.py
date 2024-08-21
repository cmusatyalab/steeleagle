import os
import zmq
from cnc_protocol import cnc_pb2

def d_server():
    context = zmq.Context()
    socket = context.socket(zmq.ROUTER)
    socket.connect('tcp://' + os.environ.get('STEELEAGLE_DRIVER_COMMAND_ADDR'))
        
    while True:
        try:
            # Receive a message from the DEALER socket
            message_parts = socket.recv_multipart()
            
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
                print("Request: take OFF")
                driver_req.resp = cnc_pb2.ResponseStatus.COMPLETED
            else:
                print("Unknown request")
                driver_req.resp = cnc_pb2.ResponseStatus.UNSUPPORTED
            
            serialized_response = driver_req.SerializeToString()
            
            # Send a reply back to the client with the identity frame and empty delimiter
            socket.send_multipart([identity, serialized_response])
            
            print(f"done processing request")
        
        except Exception as e:
            print(f"Failed to process request: {e}")
            socket.send_string("Error processing request")

if __name__ == "__main__":
    d_server()