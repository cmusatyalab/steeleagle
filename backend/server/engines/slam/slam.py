#!/usr/bin/env python3
# OpenScout
#   - Distributed Automated Situational Awareness
#
#   Author: Jingao Xu <jingaox@andrew.cmu.edu>
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

from gabriel_server.network_engine import engine_runner
from terraslam import TerraSLAMEngine
from util.utils import setup_logging

SOURCE = "telemetry"

logger = logging.getLogger(__name__)


def main():
    setup_logging(logger)
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("-p", "--port", type=int, default=9099, help="Set port number")

    parser.add_argument(
        "-s", "--server", default="128.2.208.19", help="SLAM container IP address"
    )

    # parser.add_argument(
    #     "-t", "--transform", default="transform.json", help="Path to transform.json file"
    # )

    parser.add_argument("-R", "--redis", type=int, default=6379, help="Redis port")

    parser.add_argument(
        "-a", "--auth", default="", help="Redis authentication password"
    )

    parser.add_argument(
        "-g",
        "--gabriel",
        default="tcp://gabriel-server:5555",
        help="Gabriel server endpoint",
    )

    parser.add_argument(
        "-src", "--source", default=SOURCE, help="Source for engine to register with"
    )

    args, _ = parser.parse_known_args()

    def engine_setup():
        engine = TerraSLAMEngine(args)
        return engine

    engine_runner.run(
        engine=engine_setup(),
        source_name=args.source,
        server_address=args.gabriel,
        all_responses_required=True,
    )


if __name__ == "__main__":
    main()
