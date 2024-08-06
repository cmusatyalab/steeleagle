import zmq
from cnc_protocol import cnc_pb2


def d_server():
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://*:5001")
        
   
    while True:
        try:
            # Receive a message
            message = socket.recv()
            
            # Log the raw received message
            print(f"Received raw message: {message}")
            
            # Parse the message
            driver_req = cnc_pb2.Driver()
            driver_req.ParseFromString(message)
            
            # Print parsed message and determine the response
            if driver_req.takeOff:
                print("Request: take OFF")
                response_msg = "take off response"
            else:
                print("Unknown request")
                response_msg = "Unknown request"
            
            # Send a reply back to the client
            socket.send_string(response_msg)
        
        except Exception as e:
            print(f"Failed to process request: {e}")
            socket.send_string("Error processing request")
            

if __name__ == "__main__":
    d_server()