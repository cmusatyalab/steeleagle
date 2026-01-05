# OpenScout
#   - Distributed Automated Situational Awareness
#
#   Author: Thomas Eiszler <teiszler@andrew.cmu.edu>
#
#   Copyright (C) 2020 Carnegie Mellon University
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#

import argparse
import logging
import os
import time
from abc import ABC, abstractmethod

import cv2
import numpy as np
import redis
import torch
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine, local_engine
from google.protobuf.any_pb2 import Any
from metric3d_models import Metric3DModelLoader
from metric3d_utils import Metric3DInference
from PIL import Image, ImageDraw
from steeleagle_sdk.protocol.messages import result_pb2
from steeleagle_sdk.protocol.messages import telemetry_pb2 as telemetry

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class AvoidanceEngine(ABC):
    ENGINE_NAME = "obstacle-avoidance"

    def __init__(self, args):
        self.threshold = args.threshold  # default should be 190
        self.store_detections = args.store
        self.model = args.model
        self.unittest = args.unittest
        if not self.unittest:
            self.r = redis.Redis(
                host="redis",
                port=args.redis,
                username="steeleagle",
                password=f"{args.auth}",
                decode_responses=True,
            )
            self.r.ping()
            logger.info(f"Connected to redis on port {args.redis}...")

        # timing vars
        self.count = 0
        self.lasttime = time.time()
        self.lastcount = 0
        self.lastprint = self.lasttime

        if self.store_detections:
            self.watermark = Image.open(os.getcwd() + "/watermark.png")
            self.storage_path = os.getcwd() + "/images/"
            try:
                os.makedirs(self.storage_path + "/moa")
            except FileExistsError:
                logger.info("Images directory already exists.")
            logger.info(f"Storing detection images at {self.storage_path}")

    def store_vector(self, drone, vec):
        self.r.xadd(
            "avoidance",
            {"drone_id": drone, "vector": vec},
        )

    def print_inference_stats(self):
        logger.info(f"inference time {(self.t1 - self.t0) * 1000:.1f} ms, ")
        logger.info(f"wait {(self.t0 - self.lasttime) * 1000:.1f} ms, ")
        logger.info(f"fps {1.0 / (self.t1 - self.lasttime):.2f}")
        logger.info(
            f"avg fps: {(self.count - self.lastcount) / (self.t1 - self.lastprint):.2f}"
        )
        self.lastcount = self.count
        self.lastprint = self.t1

    def process_image(self, image):
        self.t0 = time.time()
        np_data = np.frombuffer(image, dtype=np.uint8)
        img = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        actuation_vector, depth_img = self.inference(img)
        self.t1 = time.time()
        return actuation_vector, depth_img

    @abstractmethod
    def inference(self, img):
        pass

    @abstractmethod
    def load_model(self, model):
        pass

    def store_detection(self, depth_img):
        timestamp_millis = int(time.time() * 1000)
        depth_img = Image.fromarray(depth_img)
        draw = ImageDraw.Draw(depth_img)
        draw.bitmap((0, 0), self.watermark, fill=None)

        filename = str(timestamp_millis) + ".jpg"

        path = self.storage_path + "/moa/" + filename
        depth_img.save(path, format="JPEG")

        path = self.storage_path + "/moa/latest.jpg"
        depth_img.save(path, format="JPEG")

        logger.info(f"Stored image: {path}")

    def text_payload_reply(self):
        # if the payload is TEXT, say from a CNC client, we ignore
        status = gabriel_pb2.Status()
        status.code = gabriel_pb2.StatusCode.WRONG_INPUT_FORMAT
        status.message = "Ignoring text payload"
        return cognitive_engine.Result(status, None)

    def maybe_load_model(self, model):
        if model != "" and model != self.model:
            if model not in self.valid_models:
                logger.error(f"Invalid model {model}.")
            else:
                self.load_model(model)

    def handle_helper(self, input_frame):
        if input_frame.payload_type == gabriel_pb2.PayloadType.TEXT:
            return self.text_payload_reply()

        frame = telemetry.Frame()
        assert input_frame.WhichOneof("payload") == "any_payload"
        assert input_frame.any_payload.Is(telemetry.Frame.DESCRIPTOR)
        input_frame.any_payload.Unpack(frame)

        vector, depth_img = self.process_image(frame.data)
        status = gabriel_pb2.Status()

        response = result_pb2.ComputeResult()
        response.timestamp.GetCurrentTime()
        response.engine_name = self.ENGINE_NAME
        response.avoidance_result.actuation_vector = vector
        logger.info(f"Vector returned by obstacle avoidance algorithm: {vector}")
        if not self.unittest:
            self.store_vector(frame.vehicle_info.name, vector)

        if self.store_detections:
            self.store_detection(depth_img)

        self.count += 1
        if self.t1 - self.lastprint > 5:
            self.print_inference_stats()

        self.lasttime = self.t1

        any_payload = Any()
        any_payload.Pack(response)
        return cognitive_engine.Result(status, any_payload)


class MidasAvoidanceEngine(cognitive_engine.Engine, AvoidanceEngine):
    def __init__(self, args):
        super().__init__(args)

        self.valid_models = [
            "DPT_BEiT_L_512",
            "DPT_BEiT_L_384",
            "DPT_SwinV2_L_384",
            "DPT_SwinV2_B_384",
            "DPT_SwinV2_T_256",
            "DPT_Swin_L_384",
            "DPT_Next_ViT_L_384",
            "DPT_LeViT_224",
            "DPT_Large",
            "DPT_Hybrid",
            "MiDaS",
            "MiDaS_small",
        ]

        self.load_model(self.model)

    def load_model(self, model):
        logger.info(f"Fetching {self.model} MiDaS model from torch hub...")
        self.detector = torch.hub.load("intel-isl/MiDaS", model)
        self.model = model

        self.device = (
            torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        )
        self.detector.to(self.device)
        self.detector.eval()

        midas_transforms = torch.hub.load("intel-isl/MiDaS", "transforms")

        if self.model == "MiDaS_small":
            self.transform = midas_transforms.small_transform
        elif self.model in ["DPT_SwinV2_L_384", "DPT_SwinV2_B_384", "DPT_Swin_L_384"]:
            self.transform = midas_transforms.swin384_transform
        elif self.model == "MiDaS":
            self.transform = midas_transforms.default_transform
        elif self.model == "DPT_SwinV2_T_256":
            self.transform = midas_transforms.swin256_transform
        elif self.model == "DPT_LeViT_224":
            self.transform = midas_transforms.levit_transform
        elif self.model == "DPT_BEiT_L_512":
            self.transform = midas_transforms.beit512_transform
        else:
            self.transform = midas_transforms.dpt_transform
        logger.info(f"Depth predictor initialized with the following model: {model}")
        logger.info(f"Depth Threshold: {self.threshold}")

    def handle(self, input_frame):
        return self.handle_helper(input_frame)

    def inference(self, img):
        """Allow timing engine to override this"""
        # Default resolutions of the frame are obtained.The default resolutions are system dependent.
        # We convert the resolutions from float to integer.
        actuation_vector = 0
        frame_width = img.shape[1]
        frame_height = img.shape[0]
        scrapY, scrapX = frame_height // 3, frame_width // 5

        input_batch = self.transform(img).to(self.device)

        with torch.no_grad():
            prediction = self.detector(input_batch)

            prediction = torch.nn.functional.interpolate(
                prediction.unsqueeze(1),
                size=img.shape[:2],
                mode="bicubic",
                align_corners=False,
            ).squeeze()

        depth_map = prediction.cpu().numpy()

        depth_map = cv2.normalize(
            depth_map, None, 0, 1, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_64F
        )
        depth_map = (depth_map * 255).astype(np.uint8)
        full_depth_map = cv2.applyColorMap(depth_map, cv2.COLORMAP_OCEAN)

        cv2.rectangle(
            full_depth_map,
            (scrapX, scrapY),
            (full_depth_map.shape[1] - scrapX, full_depth_map.shape[0] - scrapY),
            (255, 255, 0),
            thickness=1,
        )
        depth_map[depth_map >= self.threshold] = 0
        depth_map[depth_map != 0] = 255
        depth_map = depth_map[
            scrapY : frame_height - scrapY, scrapX : frame_width - scrapX
        ]

        # convert the grayscale image to binary image
        ret, thresh = cv2.threshold(depth_map, 254, 255, 0)
        # find contours in the binary image
        contours, h = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        # full_depth_map = cv2.merge(thresh, full_depth_map)
        if contours != ():
            c = max(contours, key=cv2.contourArea)
            # calculate moments for each contour
            M = cv2.moments(c)
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
            cv2.circle(full_depth_map, (scrapX + cX, scrapY + cY), 5, (0, 255, 0), -1)
            actuation_vector = (scrapX + cX - (full_depth_map.shape[1] / 2) + 1) / (
                full_depth_map.shape[1] / 2 - scrapX
            )
            cv2.putText(
                full_depth_map,
                f"{actuation_vector:.4f}",
                (scrapX + cX, scrapY + cY - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2,
            )

        return actuation_vector, full_depth_map


class Metric3DAvoidanceEngine(cognitive_engine.Engine, AvoidanceEngine):
    def __init__(self, args):
        super().__init__(args)

        self.valid_models = [
            "metric3d_convnext_large",
            "metric3d_vit_small",
            "metric3d_vit_large",
            "metric3d_vit_giant2",
        ]

        self.inference_pipeline = None
        self.load_model(self.model)

    def load_model(self, model):
        logger.info(f"Loading Metric3D model: {model}")

        self.device = (
            torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        )

        # Load model using Metric3D model loader
        self.detector = Metric3DModelLoader.load_model(model, device=self.device)
        self.model = model

        # Initialize inference pipeline
        self.inference_pipeline = Metric3DInference(self.detector, device=self.device)

        logger.info(f"Metric3D depth predictor initialized with model: {model}")
        logger.info(f"Device: {self.device}")
        logger.info(f"Depth Threshold: {self.threshold}")

    def handle(self, input_frame):
        return self.handle_helper(input_frame)

    def inference(self, img):
        """
        Metric3D depth estimation and obstacle avoidance inference

        Args:
            img (np.ndarray): Input image in RGB format (H, W, 3)

        Returns:
            tuple: (actuation_vector, full_depth_map)
        """
        actuation_vector = 0
        frame_width = img.shape[1]
        frame_height = img.shape[0]
        scrapY, scrapX = frame_height // 3, frame_width // 5

        # Run Metric3D depth prediction
        depth_map = self.inference_pipeline.predict_depth(img)

        # Normalize depth map to 0-255 range for visualization and processing
        depth_normalized = cv2.normalize(
            depth_map, None, 0, 1, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_64F
        )
        depth_map_uint8 = (depth_normalized * 255).astype(np.uint8)

        # Create colored visualization
        full_depth_map = cv2.applyColorMap(depth_map_uint8, cv2.COLORMAP_OCEAN)

        # Draw region of interest rectangle
        cv2.rectangle(
            full_depth_map,
            (scrapX, scrapY),
            (full_depth_map.shape[1] - scrapX, full_depth_map.shape[0] - scrapY),
            (255, 255, 0),
            thickness=1,
        )

        # Apply depth threshold for obstacle detection
        # For Metric3D, we work with metric depth values
        obstacle_mask = depth_map < (
            self.threshold / 10.0
        )  # Convert threshold to metric scale

        # Convert to binary mask
        binary_mask = obstacle_mask.astype(np.uint8) * 255

        # Focus on region of interest
        roi_mask = binary_mask[
            scrapY : frame_height - scrapY, scrapX : frame_width - scrapX
        ]

        # Find contours for obstacle detection
        try:
            ret, thresh = cv2.threshold(roi_mask, 254, 255, 0)
            contours, h = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
            )

            if len(contours) > 0:
                # Find largest contour (main obstacle)
                c = max(contours, key=cv2.contourArea)

                # Calculate moments for centroid
                M = cv2.moments(c)
                if M["m00"] != 0:  # Avoid division by zero
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])

                    # Draw centroid on visualization
                    cv2.circle(
                        full_depth_map, (scrapX + cX, scrapY + cY), 5, (0, 255, 0), -1
                    )

                    # Calculate actuation vector for drone steering
                    # Positive values = turn right, negative = turn left
                    actuation_vector = (
                        scrapX + cX - (full_depth_map.shape[1] / 2) + 1
                    ) / (full_depth_map.shape[1] / 2 - scrapX)

                    # Add text annotation
                    cv2.putText(
                        full_depth_map,
                        f"{actuation_vector:.4f}",
                        (scrapX + cX, scrapY + cY - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        2,
                    )
                else:
                    logger.warning("Obstacle detected but centroid calculation failed")
            else:
                logger.debug("No obstacles detected in current frame")

        except Exception as e:
            logger.error(f"Error in obstacle detection: {e}")
            actuation_vector = 0

        return actuation_vector, full_depth_map


def main():
    """Starts the Gabriel server."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("-p", "--port", type=int, default=9099, help="Set port number")

    parser.add_argument(
        "-m",
        "--model",
        default="DPT_Large",
        help="Depth model. MiDaS: ['DPT_Large', 'DPT_Hybrid', 'MiDaS_small'], Metric3D: ['metric3d_vit_giant2', 'metric3d_vit_large', 'metric3d_vit_small', 'metric3d_convnext_large']",
    )

    parser.add_argument(
        "-r",
        "--threshold",
        type=int,
        default=190,
        help="Depth threshold for filtering.",
    )

    parser.add_argument(
        "-s",
        "--store",
        action="store_true",
        default=False,
        help="Store images with heatmap",
    )

    parser.add_argument(
        "-g",
        "--gabriel",
        default="tcp://gabriel-server:5555",
        help="Gabriel server endpoint.",
    )

    parser.add_argument(
        "-src",
        "--source",
        default="telemetry",
        help="Source for engine to register with.",
    )

    parser.add_argument(
        "-R",
        "--redis",
        type=int,
        default=6379,
        help="Set port number for redis connection [default: 6379]",
    )

    parser.add_argument("-a", "--auth", default="", help="Share key for redis user.")

    parser.add_argument(
        "-i", "--roi", type=int, default=190, help="Depth threshold for filtering."
    )

    parser.add_argument(
        "--metric3d",
        action="store_true",
        default=False,
        help="Use Metric3D for avoidance",
    )

    parser.add_argument(
        "--unittest",
        action="store_true",
        default=False,
        help="When enabled, will not connect to redis nor store images to disk.",
    )

    args, _ = parser.parse_known_args()

    def engine_factory():
        if args.metric3d:
            # Set default Metric3D model if MiDaS model is specified
            if args.model in ["DPT_Large", "DPT_Hybrid", "MiDaS_small"]:
                logger.info(
                    f"Switching from MiDaS model '{args.model}' to default Metric3D model 'metric3d_vit_giant2'"
                )
                args.model = "metric3d_vit_giant2"
            engine = Metric3DAvoidanceEngine(args)
        else:
            engine = MidasAvoidanceEngine(args)
        return engine

    engine = local_engine.LocalEngine(
        engine_factory,
        input_queue_maxsize=60,
        port=args.port,
        num_tokens=2,
        engine_id=AvoidanceEngine.ENGINE_NAME,
        use_zeromq=True,
    )

    engine.run()


if __name__ == "__main__":
    main()
