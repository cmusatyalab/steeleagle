#!/usr/bin/env python3

# Copyright (C) 2022 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import argparse
import logging

from gabriel_server.network_engine import server_runner
from util.utils import setup_logging

DEFAULT_PORT = 9099
DEFAULT_NUM_TOKENS = 2
INPUT_QUEUE_MAXSIZE = 60

logger = logging.getLogger(__name__)


def main():
    setup_logging(logger)
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-t", "--tokens", type=int, default=DEFAULT_NUM_TOKENS, help="number of tokens"
    )

    parser.add_argument(
        "-p", "--port", type=int, default=DEFAULT_PORT, help="Set port number"
    )

    parser.add_argument(
        "-q",
        "--queue",
        type=int,
        default=INPUT_QUEUE_MAXSIZE,
        help="Max input queue size",
    )

    parser.add_argument(
        "-z", "--zmq", action="store_true", help="Use ZeroMQ Gabriel client"
    )

    args, _ = parser.parse_known_args()

    server_runner.run(
        websocket_port=args.port,
        zmq_address="tcp://*:5555",
        num_tokens=args.tokens,
        input_queue_maxsize=args.queue,
        use_zeromq=args.zmq,
    )


if __name__ == "__main__":
    main()
