#!/usr/bin/env python3
# Copyright (C) 2026 Carnegie Mellon University
# Licensed under the Apache License, Version 2.0 (the "License");
#
# Runner for the SwiftMap cognitive engine. Targets the modern Gabriel API
# (EngineRunner + engine_id), matching the aruco / telemetry engines.

import argparse
import logging

from gabriel_server.network_engine import engine_runner

from swiftmap_engine import SwiftMapEngine

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
        "-src", "--engine_id", default="swiftmap_engine", help="Engine identifier."
    )

    parser.add_argument(
        "-s",
        "--server",
        default="swiftmap",
        help="SwiftMap mapping server hostname / IP.",
    )

    parser.add_argument(
        "--server_port",
        type=int,
        default=43322,
        help="SwiftMap mapping server TCP port.",
    )

    args, _ = parser.parse_known_args()

    logger.info("Starting SwiftMap cognitive engine...")
    runner = engine_runner.EngineRunner(
        engine=SwiftMapEngine(args),
        engine_id=args.engine_id,
        server_address=args.gabriel,
        all_responses_required=False,
    )

    runner.run()


if __name__ == "__main__":
    main()
