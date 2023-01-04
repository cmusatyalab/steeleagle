#!/usr/bin/env python3

# Copyright 2022 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import argparse
from gabriel_client.websocket_client import WebsocketClient
import logging
from drone_adapter import DroneAdapter
import randomname

DRONE_ID = randomname.get_name(adj=('weather', 'materials',), noun=('birds',))
WEBSOCKET_PORT = 9099
DEFAULT_SOURCE_NAME = 'command'

logger = logging.getLogger(__name__)


def preprocess(frame):
    return frame


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--server', default='gabriel-server',
                        help='Specify address of Steel Eagle CNC server [default: gabriel-server')
    parser.add_argument('-p', '--port', default='9099',
                        help='Specify websocket port [default: 9099]')
    parser.add_argument('-t', '--timeout', default=10,
                        help='Disconnect after N seconds [default: 10')
    parser.add_argument('-l', '--loglevel', default='INFO',
                        help='Set the log level')

    args = parser.parse_args()
    logging.basicConfig(format="%(levelname)s: %(message)s",
                        level=args.loglevel)
    adapter = DroneAdapter(preprocess, DEFAULT_SOURCE_NAME, DRONE_ID)

    client = WebsocketClient(
        args.server, args.port,
        adapter.get_producer_wrappers(), adapter.consumer
    )
    client.launch()


if __name__ == '__main__':
    main()
