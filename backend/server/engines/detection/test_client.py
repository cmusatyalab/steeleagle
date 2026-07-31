#!/usr/bin/env python3

import argparse
import asyncio
import logging
import os
import random
import time

import cv2
from gabriel_client.zeromq_client import InputProducer, ZeroMQClient
from gabriel_protocol import gabriel_pb2
from google.protobuf.any_pb2 import Any
from steeleagle_protocol.v1 import common_pb2
from steeleagle_protocol.v1.messages.telemetry import telemetry_pb2 as telemetry

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
        self.engine_id = args.engine

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

    def process_results(self, result):
        if not result:
            return

        # Get engine ID
        engine_id = result.target_engine_id
        logger.info(f"Received result from engine: {engine_id}")

        if result.string_result:
            payload = result.string_result.decode("utf-8")
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
                # input_frame.byte_payload =jpg_buffer.tobytes()

                extras = telemetry.EncodedFrame()
                extras.encoded_data = jpg_buffer.tobytes()
                extras.timestamp.GetCurrentTime()
                extras.id = FRAME_ID
                extras.position_info.global_position.latitude = (
                    self.latitude + random.uniform(0.0005, 0.001)
                )
                extras.position_info.global_position.longitude = (
                    self.longitude + random.uniform(0.0005, 0.001)
                )
                extras.position_info.relative_position.z = self.altitude
                extras.gimbal_status.pose_body.pitch = self.gimbal_pitch

                FRAME_ID += 1
                # Pack extras into the input frame
                input_frame.any_payload.Pack(extras)

                logger.debug(
                    f"Image producer: finished preparing frame at {time.time()}"
                )
            except AttributeError as e:
                input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
                input_frame.string_payload = f"Unable to produce a frame: {e}"
                raise e

            return input_frame

        return [
            InputProducer(
                producer=producer,
                producer_name=self.source_name,
                target_engine_ids=[self.engine_id],
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
    ap.add_argument(
        "-e",
        "--engine",
        default="object-engine",
        help="Target engine id [default=object-engine]",
    )
    args = ap.parse_args()

    test_adapter = TestAdapter(args)

    client_info = Any()
    client_info.Pack(common_pb2.VehicleInfo(vehicle_id=args.client_id))
    client = ZeroMQClient(
        f"tcp://{args.server}:{args.port}",
        test_adapter.get_producer_wrappers(),
        test_adapter.process_results,
        client_info=client_info,
    )
    client.launch()


if __name__ == "__main__":
    main()
