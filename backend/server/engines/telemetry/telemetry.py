#!/usr/bin/env python3

# Copyright (C) 2022 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import argparse
import logging

from gabriel_server.network_engine.engine_runner import EngineRunner
from telemetry_engine import TelemetryEngine
import logging

SOURCE = "telemetry"
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

    parser.add_argument("-p", "--port", type=int, default=9099, help="Set port number")

    parser.add_argument(
        "-g",
        "--gabriel",
        default="tcp://gabriel-server:5555",
        help="Gabriel server endpoint.",
    )

    parser.add_argument(
        "-r",
        "--redis",
        type=int,
        default=6379,
        help="Set port number for redis connection [default: 6379]",
    )

    parser.add_argument("-a", "--auth", default="", help="Share key for redis user.")

    parser.add_argument(
        "-l", "--publish", action="store_true", help="Publish incoming images via redis"
    )

    parser.add_argument(
        "-t",
        "--ttl",
        type=int,
        default=7,
        help="TTL in days before drones status tables are cleaned up in redis [default: 7]",
    )

    args, _ = parser.parse_known_args()

    def engine_setup():
        return TelemetryEngine(args)

    logger.info("Starting telemetry cognitive engine..")
    engine_runner = EngineRunner(
        engine=engine_setup(),
        engine_id=SOURCE,
        server_address=args.gabriel,
        all_responses_required=True,
    )
    engine_runner.run()


if __name__ == "__main__":
    main()
