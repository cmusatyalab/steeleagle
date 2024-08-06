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
        print(f'start_mission message:{message}')
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

    # Interactive command input loop
    while True:
        user_input = input("Enter 'start' to start the mission or 'stop' to stop the mission (type 'exit' to quit): ").strip().lower()
        if user_input == 'start':
            send_start_mission()
        elif user_input == 'stop':
            send_stop_mission()
        elif user_input == 'exit':
            print("Exiting client.")
            break
        else:
            print("Invalid command.")

if __name__ == "__main__":
    print("Starting client")
    k_client()