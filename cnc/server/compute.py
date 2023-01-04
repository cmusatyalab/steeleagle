#!/usr/bin/env python3

# Copyright (C) 2022 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

from gabriel_server.network_engine import engine_runner
from compute_engine import DroneComputeEngine
import logging
import argparse

SOURCE = 'compute'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-g", "--gabriel",  default="tcp://gabriel-server:5555", help="Gabriel server endpoint."
    )

    args, _ = parser.parse_known_args()

    def engine_setup():
        return DroneComputeEngine(args)
        
    logger.info("Starting Drone Compute cognitive engine..")
    engine_runner.run(engine=engine_setup(), source_name=SOURCE, server_address=args.gabriel, all_responses_required=True)

if __name__ == "__main__":
    main()
