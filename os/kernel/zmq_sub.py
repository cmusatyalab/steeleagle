import zmq

def subscriber():
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect("tcp://127.0.0.1:5555")  # Connect to publisher
    socket.setsockopt_string(zmq.SUBSCRIBE, "")  # Subscribe to all topics

    print("Subscriber started...")
    while True:
        message = socket.recv_string()
        print(f"Received: {message}")

if __name__ == "__main__":
    subscriber()

