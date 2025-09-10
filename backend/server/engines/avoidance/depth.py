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

from gabriel_server.network_engine import engine_runner
from obstacle_avoidance_engine import Metric3DAvoidanceEngine, MidasAvoidanceEngine
from util.utils import setup_logging

SOURCE = "openscout"

logger = logging.getLogger(__name__)


def main():
    setup_logging(logger)
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
        "-src", "--source", default=SOURCE, help="Source for engine to register with."
    )

    parser.add_argument(
        "-f",
        "--faux",
        action="store_true",
        default=False,
        help="Generate faux vectors using the file specfied instead of results from MiDaS.",
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

    args, _ = parser.parse_known_args()

    def engine_setup():
        if args.metric3d:
            # Set default Metric3D model if MiDaS model is specified
            if args.model in ["DPT_Large", "DPT_Hybrid", "MiDaS_small"]:
                logger.info(f"Switching from MiDaS model '{args.model}' to default Metric3D model 'metric3d_vit_giant2'")
                args.model = "metric3d_vit_giant2"
            engine = Metric3DAvoidanceEngine(args)
        else:
            engine = MidasAvoidanceEngine(args)
        return engine

    engine_runner.run(
        engine=engine_setup(),
        source_name=args.source,
        server_address=args.gabriel,
        all_responses_required=True,
    )


if __name__ == "__main__":
    main()
