#!/usr/bin/env python3

# Copyright 2022 Carnegie Mellon University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
from gabriel_client.websocket_client import WebsocketClient
from commander_adapter import CommanderAdapter
import logging
import randomname

COMMANDER_ID = randomname.get_name(adj=('age',), noun=('military_army', 'military_navy'))
WEBSOCKET_PORT = 9099
DEFAULT_SOURCE_NAME = 'command'

logger = logging.getLogger(__name__)

def preprocess(frame):
    return frame

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--server', default='cloudlet040.elijah.cs.cmu.edu',
        help='Specify address of Steel Eagle CNC server [default: cloudlet040.elijah.cs.cmu.edu')
    parser.add_argument('-p', '--port', default='9099', help='Specify websocket port [default: 9099]')
    parser.add_argument('-l', '--loglevel', default='INFO', help='Set the log level')
    
    args = parser.parse_args()
    logging.basicConfig(format="%(levelname)s: %(message)s", level=args.loglevel)
    adapter = CommanderAdapter(preprocess, DEFAULT_SOURCE_NAME, COMMANDER_ID)

    client = WebsocketClient(
        args.server, args.port,
        adapter.get_producer_wrappers(), adapter.consumer
    )

    client.launch()

    

if __name__ == '__main__':
    main()