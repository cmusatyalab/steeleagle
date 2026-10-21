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
from swiftmap_engine import SwiftMapEngine

ENGINE_NAME = "swiftmap"
# The engine answers with no result yet, so it needs only a small output
# buffer, still enough for the TODO GenericResult in SwiftMapEngine.handle.
MAX_OUTPUT_SIZE = 1024
# How often the engine checks whether it was asked to stop, in seconds.
STOP_CHECK_INTERVAL_S = 0.5

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
    
    parser.add_argument(
        "-n",
        "--name",
        default=ENGINE_NAME,
        help="The engine's name. The gabriel-server on this machine must serve it.",
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

    parser.add_argument(
        "--send-distance",
        dest="send_distance",
        type=float,
        default=float(os.environ.get("SWIFTMAP_SEND_DISTANCE", "5.0")),
        help="Forward at most one frame+GPS pair per this many meters of travel "
        "(0 = forward every frame).",
    )

    args, _ = parser.parse_known_args()
    gabriel.init_log()
    swiftmap_engine = SwiftMapEngine(args)
    stopping = threading.Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopping.set())

    logger.info(f"Starting SwiftMap cognitive engine {args.name}...")
    try:
        with gabriel.Engine(args.name, max_output_size=MAX_OUTPUT_SIZE) as engine:
            while not stopping.is_set():
                engine_input = engine.next(timeout=STOP_CHECK_INTERVAL_S)
                if engine_input is None:
                    continue
                try:
                    swiftmap_engine.handle(engine_input)
                except Exception:
                    logger.exception(f"Failed to process an input from {engine_input.id.producer}")
                finally:
                    engine.stop()
    finally:
        swiftmap_engine.cleanup()

if __name__ == "__main__":
    main()
