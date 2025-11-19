#!/usr/bin/env python3

import argparse
import asyncio
import logging
import os
import time

import cv2
from steeleagle_sdk.protocol.messages import result_pb2
from steeleagle_sdk.protocol.messages import telemetry_pb2 as telemetry
from gabriel_client.zeromq_client import InputProducer, ZeroMQClient
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine
from google.protobuf import text_format

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FRAME_ID = 0


class TestAdapter:
    def __init__(
        self,
        args,
    ):
        self.source_name = args.source
        self.server = args.server
        self.port = args.port
        self.client_id = args.client_id

        self.latitude = args.lat
        self.longitude = args.lon
        self.altitude = args.alt
        self.heading = args.heading
        self.gimbal_pitch = args.pitch
        self.model = args.model

        image_path = args.image
        # Setup image source
        if os.path.isdir(image_path):
            self.image_files = sorted(
                [
                    os.path.join(image_path, f)
                    for f in os.listdir(image_path)
                    if f.lower().endswith((".png", ".jpg", ".jpeg"))
                ]
            )
            if not self.image_files:
                raise ValueError(f"No image files found in {image_path}")
            logger.info(f"Found {len(self.image_files)} images")
            self.idx = 0
            self.is_dir = True
        else:
            self.image = cv2.imread(image_path)
            if self.image is None:
                raise ValueError(f"Cannot read {image_path}")
            self.is_dir = False

    def process_results(self, result_wrapper):
        if len(result_wrapper.results) == 0:
            return

        # Get engine ID
        engine_id = result_wrapper.result_producer_name.value
        logger.info(
            f"Received {len(result_wrapper.results)} results from engine: {engine_id}"
        )

        extras = cognitive_engine.unpack_extras(
            result_pb2.ComputeResult, result_wrapper
        )
        logger.info(f"=====Extras=====\t{text_format.MessageToString(extras)}")
        for result in result_wrapper.results:
            if result.payload_type == gabriel_pb2.PayloadType.TEXT:
                payload = result.payload.decode("utf-8")
                logger.info(f"=====result.payload=====\t{payload}")

    def get_producer_wrappers(self):
        async def producer():
            global FRAME_ID
            await asyncio.sleep(0.1)

            logger.debug(f"Image producer: starting at {time.time()}")
            input_frame = gabriel_pb2.InputFrame()

            try:
                if self.is_dir:
                    img_path = self.image_files[self.idx]
                    img = cv2.imread(img_path)
                    self.idx = (self.idx + 1) % len(self.image_files)
                    logger.info(f"Sending {img_path}")
                else:
                    img = self.image

                _, jpg_buffer = cv2.imencode(".jpg", img)
                input_frame.payload_type = gabriel_pb2.PayloadType.IMAGE
                input_frame.payloads.append(jpg_buffer.tobytes())

                extras = telemetry.Frame()
                extras.data = jpg_buffer.tobytes()
                extras.timestamp.GetCurrentTime()
                height, width, channels = img.shape
                extras.h_res = height
                extras.v_res = width
                extras.d_res = 0
                extras.channels = channels
                extras.id = FRAME_ID
                extras.vehicle_info.name = self.client_id
                extras.position_info.global_position.latitude = self.latitude
                extras.position_info.global_position.longitude = self.longitude
                extras.position_info.relative_position.z = self.altitude
                gimbal = telemetry.GimbalStatus()
                gimbal.pose_body.pitch = self.gimbal_pitch
                extras.gimbal_info.gimbals.append(gimbal)

                FRAME_ID += 1
                # Pack extras into the input frame
                input_frame.extras.Pack(extras)

                logger.debug(
                    f"Image producer: finished preparing frame at {time.time()}"
                )
            except Exception as e:
                input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
                input_frame.payloads.append(f"Unable to produce a frame: {e}".encode())
                logger.error(f"Image producer: unable to produce a frame: {type(e)}")

            return input_frame

        return [
            InputProducer(
                producer=producer,
                source_name=self.source_name,
                target_engine_ids="openscout-object",
            )
        ]

    async def run(self):
        logger.info(f"Starting ZeroMQ client connecting to {self.server}:{self.port}")
        logger.info("Will collect results from all available engines")
        await self.gabriel_client.launch_async()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--image", required=True, help="image file or directory")
    ap.add_argument("--lat", required=True, type=float, help="Latitude of vehicle")
    ap.add_argument("--lon", required=True, type=float, help="Longitude of vehicle")
    ap.add_argument(
        "--alt", required=True, type=float, help="Altitude of vehicle (AGL)"
    )
    ap.add_argument(
        "--heading", required=True, type=float, help="Heading of vehicle (0-360)"
    )
    ap.add_argument(
        "--model", required=True, help="Model to use in the detection engine"
    )
    ap.add_argument("--pitch", required=True, type=int, help="Gimbal pitch angle")
    ap.add_argument("-s", "--server", default="gabriel-server", help="server host")
    ap.add_argument("-p", "--port", type=int, default=9099, help="server port")
    ap.add_argument("-n", "--source", default="telemetry", help="source name")
    ap.add_argument(
        "-c", "--client_id", default="canary", help="client id for drone_id"
    )
    args = ap.parse_args()

    test_adapter = TestAdapter(args)

    client = ZeroMQClient(
        f"tcp://localhost:{args.port}",
        test_adapter.get_producer_wrappers(),
        test_adapter.process_results,
    )
    client.launch()


if __name__ == "__main__":
    main()
