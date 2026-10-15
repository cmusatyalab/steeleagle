#!/usr/bin/env python3
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
import signal
import threading

import gabriel
from openscout_object_engine import DETECTION_RESULT_TYPE, OpenScoutObjectEngine

ENGINE_NAME = "detector"
# The largest DetectionResult the engine returns: room for hundreds of
# detections. Gabriel reserves shared memory for it.
MAX_OUTPUT_SIZE = 64 * 1024
# How often the engine checks whether it was asked to stop, in seconds.
STOP_CHECK_INTERVAL_S = 0.5

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-n",
        "--name",
        default=ENGINE_NAME,
        help="The engine's name. The gabriel-server on this machine must serve it.",
    )

    parser.add_argument(
        "-m",
        "--model",
        default="coco",
        help="Model to load, from the model/ directory: <name>.pt, or <name>.json for another architecture.",
    )

    parser.add_argument(
        "-r", "--threshold", type=float, default=0.85, help="Confidence threshold"
    )

    parser.add_argument(
        "-s",
        "--store",
        action="store_true",
        default=False,
        help="Store images with bounding boxes",
    )

    parser.add_argument(
        "-x",
        "--exclude",
        help="Comma separated list of classes (ids) to exclude when performing detection.",
    )

    parser.add_argument(
        "--redis-host", default="redis", help="Host name of the redis server."
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
        "-hsv",
        "--hsv_threshold",
        type=float,
        default=5.0,
        help="HSV filter threshold [0.0-100.0]",
    )

    parser.add_argument(
        "--radius",
        type=float,
        default=5.0,
        help="Radius in meters to consider when looking for previously found objects.",
    )

    parser.add_argument(
        "--ttl",
        type=int,
        default=1200,
        help="TTL in seconds before objects are cleaned up in redis [default: 1200]",
    )

    parser.add_argument(
        "--geofence",
        default="geofence.kml",
        help="Path to KML file on the shared volume that specified the geofence. [default: geofence.kml]",
    )

    parser.add_argument(
        "--geofence_enabled",
        action="store_true",
        default=False,
        help="Whether to use a geofence to decide whether to store detections",
    )

    parser.add_argument(
        "--unittest",
        action="store_true",
        default=False,
        help="When enabled, will not connect to redis nor store images to disk.",
    )
    args, _ = parser.parse_known_args()

    gabriel.init_log()
    detector = OpenScoutObjectEngine(args)

    # The engine waits in Gabriel's C library, where Python can't interrupt it,
    # so it waits in short steps and checks for a stop in between.
    stopping = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopping.set())

    logger.info(f"Starting object detection cognitive engine {args.name}..")
    with gabriel.Engine(
        args.name, result_type=DETECTION_RESULT_TYPE, max_output_size=MAX_OUTPUT_SIZE
    ) as engine:
        while not stopping.is_set():
            engine_input = engine.next(timeout=STOP_CHECK_INTERVAL_S)
            if engine_input is None:
                continue
            result = None
            try:
                result = detector.handle(engine_input)
            except Exception:
                logger.exception(
                    f"Failed to process an input from {engine_input.id.producer}"
                )
            finally:
                engine.stop(result or b"")


if __name__ == "__main__":
    main()
