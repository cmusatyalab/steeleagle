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
            if driver_req.HasField('getCameras'):
                print("Request: getCameras")
                response_msg = "getCameras response"
            elif driver_req.HasField('switchCameras'):
                print("Request: switchCameras")
                response_msg = "switchCameras response"
            elif driver_req.HasField('takeOff'):
                print("Request: takeOff")
                response_msg = "takeOff response"
            elif driver_req.HasField('setAttitude'):
                print("Request: setAttitude")
                response_msg = "setAttitude response"
            elif driver_req.HasField('setVelocity'):
                print("Request: setVelocity")
                response_msg = "setVelocity response"
            elif driver_req.HasField('setRelativePosition'):
                print("Request: setRelativePosition")
                response_msg = "setRelativePosition response"
            elif driver_req.HasField('setTranslation'):
                print("Request: setTranslation")
                response_msg = "setTranslation response"
            elif driver_req.HasField('setGlobalPosition'):
                print("Request: setGlobalPosition")
                response_msg = "setGlobalPosition response"
            elif driver_req.HasField('hover'):
                print("Request: hover")
                response_msg = "hover response"
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