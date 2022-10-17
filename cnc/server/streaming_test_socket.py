import socket
import cv2
import numpy as np
import time
import zmq
import argparse
import sys

HOST=''
PORT=8485
LOC = {'latitude': 40.4136589, 'longitude': -79.9495332, 'altitude': 10}

# Required for sending image over zmq
def send_array(sock, A, flags=0, copy=True, track=False):
    """send a numpy array with metadata"""
    global LOC
    md = dict(
        dtype = str(A.dtype),
        shape = A.shape,
        location = LOC,
        model = 'robomaster'
    )
    sock.send_json(md, flags|zmq.SNDMORE)
    return sock.send(A, flags, copy=copy, track=track)


def recv_from_nonblocking(fd: socket, size: int) -> bytes:
  buf, received = [], 0
  while received < size:
    buf.append(fd.recv(size - received))
    received += len(buf[-1])
  return b"".join(buf)

def _main():

    parser = argparse.ArgumentParser(prog='test_socket', 
        description='Receives image frames from Android streaming test app.')
    parser.add_argument('-p', '--port', default=8485,
        help='Specify port to listen on [default: 8485]')
    parser.add_argument('-zp', '--zmq_port', default=5555,
        help='Specify zmq port to publish to [default: 5555]')
    parser.add_argument('-s', '--store', action='store_true', 
        help='Store images locally on disk [default: False]')
    parser.add_argument('-z', '--zmq', action='store_true', 
        help='Send images over zmq to OpenScout (assumes OpenScout is listening locally) [default: False]')

    args = parser.parse_args()


    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST,args.port))
    print(f'Socket bound to port: {args.port}')
    s.listen(10)
    print('Socket now listening...')

    conn,addr=s.accept()
    data = b""
    if(args.zmq):
        context = zmq.Context()

    try:
        with conn:
            if(args.zmq):
                print(f"Publishing images for OpenScout client's ZmqAdapter on port {args.zmq_port}..")
                zmq_socket = context.socket(zmq.PUB)
                zmq_socket.bind(f'tcp://*:{args.zmq_port}')

            print(f"Client connected {addr}")
            frames_received = 0
            start = time.time()
            lastprint = start
            lastcount = 0
            while True:
                start = time.time()
                header = recv_from_nonblocking(conn, 4)
                size = int.from_bytes(header, "big")
                print(f"About to receive an image of {size} bytes...")
                data = recv_from_nonblocking(conn, size)
                frames_received += 1
                print(f"Frames Received: {frames_received} Data Length: {len(data)}")

                now = time.time()
                if now - lastprint > 5:
                    print(
                        "avg fps: {0:.2f}".format(
                            (frames_received - lastcount) / 5)
                        )
                    print()
                    lastcount = frames_received
                    lastprint = now

                frame = cv2.imdecode(np.fromstring(data, np.uint8), cv2.IMREAD_COLOR)
                #cv2frame = cv2.cvtColor(frame.as_ndarray(), cv2.COLOR_YUV2BGR_I420)
                if(args.zmq):
                    print(f"Publishing frame {frames_received} to OpenScout client...")
                    send_array(zmq_socket, frame)

                if(args.store):
                    cv2.imwrite(f'{frames_received}.jpg', frame)
                cv2.imshow('server',frame)
                cv2.waitKey(1)

    except KeyboardInterrupt:
        s.close()
        print('Socket closed')

if __name__ == "__main__":
    _main()
