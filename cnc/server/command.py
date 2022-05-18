#!/usr/bin/env python3
# CommandAndControl
#   - Platform Agnostic Automated Drone Control
#
#   Author: Thomas Eiszler <teiszler@andrew.cmu.edu>
#
#   Copyright (C) 2022 Carnegie Mellon University
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

    args, _ = parser.parse_known_args()

    def engine_setup():
        return DroneCommandEngine(args)

    logger.info("Starting Drone Command cognitive engine..")
    engine_runner.run(engine=engine_setup(), source_name=SOURCE, server_address=args.gabriel, all_responses_required=True)

if __name__ == "__main__":
    main()
