#!/usr/bin/env python3

# Copyright (C) 2022 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import argparse
import logging
import os
import signal
import threading

import gabriel
from telemetry_engine import TelemetryEngine

ENGINE_NAME = "telemetry"
# The engine forwards nothing and answers with no result, so it needs only a
# small output buffer.
MAX_OUTPUT_SIZE = 1024
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
        "--redis-host", default="redis", help="Host name of the redis server."
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
        "-s",
        "--storage",
        default=os.path.join(os.getcwd(), "images"),
        help="Directory to store images and MCAP recordings in.",
    )

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

    gabriel.init_log()
    telemetry_engine = TelemetryEngine(args)

    # The engine waits in Gabriel's C library, where Python can't interrupt it,
    # so it waits in short steps and checks for a stop in between.
    stopping = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopping.set())

    logger.info(f"Starting telemetry cognitive engine {args.name}..")
    try:
        with gabriel.Engine(args.name, max_output_size=MAX_OUTPUT_SIZE) as engine:
            while not stopping.is_set():
                engine_input = engine.next(timeout=STOP_CHECK_INTERVAL_S)
                if engine_input is None:
                    continue
                try:
                    telemetry_engine.handle(engine_input)
                except Exception:
                    logger.exception(f"Failed to process an input from {engine_input.id.producer}")
                finally:
                    engine.drop()
    finally:
        telemetry_engine.cleanup()


if __name__ == "__main__":
    main()
