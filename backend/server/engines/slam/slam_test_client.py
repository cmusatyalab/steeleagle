#!/usr/bin/env python3
import argparse, logging, os, cv2, asyncio, time
from gabriel_client.websocket_client import WebsocketClient, ProducerWrapper
from gabriel_protocol import gabriel_pb2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImageProducer:
    def __init__(self, image_path, source_name="openscout"):
        self.source_name = source_name
        if os.path.isdir(image_path):
            self.image_files = sorted([os.path.join(image_path, f)
                                       for f in os.listdir(image_path)
                                       if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
            if not self.image_files:
                raise ValueError(f"No image files found in {image_path}")
            logger.info("Found %d images", len(self.image_files))
            self.idx = 0
            self.is_dir = True
        else:
            self.image = cv2.imread(image_path)
            if self.image is None:
                raise ValueError(f"Cannot read {image_path}")
            self.is_dir = False

    async def __call__(self):
        """Async producer coroutine expected by ProducerWrapper."""
        if self.is_dir:
            img_path = self.image_files[self.idx]
            img = cv2.imread(img_path)
            self.idx = (self.idx + 1) % len(self.image_files)
            logger.info("Sending %s", img_path)
        else:
            img = self.image

        _, buf = cv2.imencode(".jpg", img)
        frame = gabriel_pb2.InputFrame()
        frame.payload_type = gabriel_pb2.PayloadType.IMAGE
        frame.payloads.append(buf.tobytes())

        await asyncio.sleep(0.1)
        return frame

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--image", required=True, help="image file or dir")
    ap.add_argument("-s", "--server", default="gabriel-server", help="server host")
    args = ap.parse_args()

    prod = ImageProducer(args.image)
    wrapper = ProducerWrapper(producer=prod, source_name=prod.source_name)

    client = WebsocketClient(host=args.server,
                             port=9099,
                             producer_wrappers=[wrapper],
                             consumer=None)
    client.launch()         
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()