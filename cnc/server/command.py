#!/usr/bin/env python3

# Copyright (C) 2022 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

from gabriel_server.network_engine import engine_runner
from command_engine import DroneCommandEngine
import logging
import argparse

SOURCE = 'command'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-p", "--port", type=int, default=9099, help="Set port number"
    )

    parser.add_argument(
        "-t", "--timeout", type=int, default=300, help="Invalidate drones after this many seconds [default: 300]"
    )

    parser.add_argument(
        "-g", "--gabriel",  default="tcp://gabriel-server:5555", help="Gabriel server endpoint."
    )

    parser.add_argument(
        "-s", "--store", action="store_true", default=False, help="Store received images."
    )


    args, _ = parser.parse_known_args()

    def engine_setup():
        return DroneCommandEngine(args)

    logger.info("Starting Drone Command cognitive engine..")
    engine_runner.run(engine=engine_setup(), source_name=SOURCE, server_address=args.gabriel, all_responses_required=True)

if __name__ == "__main__":
    main()
