import zmq
import time
from cnc_protocol import cnc_pb2

def k_client():
    # Create a ZMQ context and a REQ (request) socket
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect("tcp://localhost:5000")  # Connect to the server

    # Function to send a start mission command
    def send_start_mission():
        mission_command = cnc_pb2.Mission()
        mission_command.startMission = True
        message = mission_command.SerializeToString()
        socket.send(message)
        reply = socket.recv_string()
        print(f"Server reply: {reply}")

    # Function to send a stop mission command
    def send_stop_mission():
        mission_command = cnc_pb2.Mission()
        mission_command.stopMission = True
        message = mission_command.SerializeToString()
        socket.send(message)
        reply = socket.recv_string()
        print(f"Server reply: {reply}")

    # Example usage
    send_start_mission()
    time.sleep(10)  # Wait for 10 seconds
    send_stop_mission()

if __name__ == "__main__":
    k_client()