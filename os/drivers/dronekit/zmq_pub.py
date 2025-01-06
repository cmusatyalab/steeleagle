import zmq
import time

def publisher():
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind("tcp://*:5555")  # Bind to port 5555

    print("Publisher started...")
    while True:
        message = "Hello from publisher!"
        print(f"Sending: {message}")
        socket.send_string(message)
        time.sleep(1)  # Send a message every second

if __name__ == "__main__":
    publisher()

