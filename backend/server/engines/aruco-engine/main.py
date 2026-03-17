#!/usr/bin/env python3
#   Author: Aditya Chanana <achanana@andrew.cmu.edu>
#
#   Copyright (C) 2026 Carnegie Mellon University
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

from gabriel_server.network_engine import engine_runner
from aruco_marker_detector_engine import ArucoMarkerDetectorEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-p", "--port", type=int, default=9099, help="Set port number")

    parser.add_argument(
        "-g",
        "--gabriel",
        default="tcp://gabriel-server:5555",
        help="Gabriel server endpoint.",
    )

    parser.add_argument(
        "-src", "--engine_id", default="aruco_detector_engine", help="Engine identifier."
    )

    args, _ = parser.parse_known_args()

    logger.info("Starting object detection cognitive engine..")
    runner = engine_runner.EngineRunner(
        engine=ArucoMarkerDetectorEngine(),
        engine_id=args.engine_id,
        server_address=args.gabriel,
        all_responses_required=True,
    )

    runner.run()

if __name__ == "__main__":
    main()
