#!/usr/bin/env python3
import argparse
import sys
import argparse
import cv2
import numpy as np
import zmq
from steeleagle_sdk.protocol.messages.telemetry_pb2 import Frame


def main():
    parser = argparse.ArgumentParser(
        prog="Imagery Viewer",
        description="Subscribe to imagery frames over ZMQ and display with OpenCV",
    )
    parser.add_argument(
        "-i",
        "--imagery-addr",
        default="ipc:///tmp/imagery.sock",
        help="ZMQ SUB address for imagery (e.g., ipc:///tmp/imagery.sock, tcp://127.0.0.1:5557)",
    )
    parser.add_argument(
        "--rgb",
        action="store_true",
        help="Interpret incoming frames as RGB and convert to OpenCV BGR for display",
    )
    args = parser.parse_args()

    addr = args.imagery_addr

    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.SUB)
    sock.connect(addr)
    sock.setsockopt_string(zmq.SUBSCRIBE, "")  # subscribe to all

    print(f"[viewer] Connected to {addr}")

    win = "Imagery Viewer (press 'q' to quit)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    try:
        while True:
            parts = sock.recv_multipart()
            if len(parts) == 1:
                data = parts[0]
            else:
                _, data = parts[:2]

            raw_frame = Frame()
            raw_frame.ParseFromString(data)

            frame_bytes = np.frombuffer(raw_frame.data, dtype=np.uint8)

            expected = raw_frame.v_res * raw_frame.h_res * raw_frame.channels
            if frame_bytes.size != expected:
                print(
                    f"[viewer] Size mismatch: got {frame_bytes.size}, expected {expected}",
                    file=sys.stderr,
                )
                continue

            img = frame_bytes.reshape(
                raw_frame.v_res,
                raw_frame.h_res,
                raw_frame.channels,
            )

            if args.rgb:
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

            cv2.imshow(win, img)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

    except KeyboardInterrupt:
        print("\n[viewer] Interrupted, exiting...")
    finally:
        cv2.destroyAllWindows()
        sock.close()
        # If you used Context.instance(), don't term it unless you own the process-wide ctx.
        # ctx.term()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Viewer",
        description="Gives a view for vehicle imagery",
    )
    parser.add_argument(
        "-a",
        "--addr",
        default="unix:///ipc/imagery.sock",
        help="Address of the driver imagery",
    )
    args = parser.parse_args()

    main(args.addr.replace('unix', 'ipc'))
