#!/usr/bin/env python3
import sys

import cv2
import numpy as np
import zmq
from steeleagle_sdk.protocol.messages.telemetry_pb2 import Frame


def main():
    addr = "ipc:///tmp/imagery.sock"  # or tcp://127.0.0.1:5557 etc.

    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.SUB)
    sock.connect(addr)
    sock.setsockopt_string(zmq.SUBSCRIBE, "")  # subscribe to all

    print(f"[viewer] Connected to {addr}")

    win = "Imagery Viewer (press 'q' to quit)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    try:
        while True:
            # Your producer:  _, data = await imagery_sock.recv_multipart()
            parts = sock.recv_multipart()
            if len(parts) == 1:
                data = parts[0]
            else:
                _, data = parts[:2]

            raw_frame = Frame()
            raw_frame.ParseFromString(data)

            # raw_frame.data is raw uint8 buffer: v_res × h_res × channels
            frame_bytes = np.frombuffer(raw_frame.data, dtype=np.uint8)

            expected = raw_frame.v_res * raw_frame.h_res * raw_frame.channels
            if frame_bytes.size != expected:
                print(
                    f"[viewer] Size mismatch: got {frame_bytes.size}, "
                    f"expected {expected}",
                    file=sys.stderr,
                )
                continue

            img = frame_bytes.reshape(
                raw_frame.v_res,
                raw_frame.h_res,
                raw_frame.channels,
            )

            # If the source is RGB and you want OpenCV's BGR:
            # img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

            cv2.imshow(win, img)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

    except KeyboardInterrupt:
        print("\n[viewer] Interrupted, exiting...")
    finally:
        cv2.destroyAllWindows()
        sock.close()
        ctx.term()


if __name__ == "__main__":
    main()
