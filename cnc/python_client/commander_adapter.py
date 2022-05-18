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

import os
import numpy as np
from gabriel_protocol import gabriel_pb2
from gabriel_client.websocket_client import ProducerWrapper
import logging
from cnc_protocol import cnc_pb2
import asyncio

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class CommanderAdapter:
    def __init__(self, preprocess, source_name, id):
        '''
        preprocess should take one frame parameter
        produce_engine_fields takes no parameters
        consume_frame should take one frame parameter and one engine_fields
        parameter
        '''
        self.id = id
        self._preprocess = preprocess
        self._source_name = source_name
        self.frames_processed = 0

    def get_producer_wrappers(self):
        async def producer():
            await asyncio.sleep(2)
            print('1. Halt (killswitch)')
            print('2. Send Script URL')
            print('Enter the number of the command you wish to send:')
            selection = int(input())
            if selection == 2:
                print('Enter the URL where the script resides (i.e http://cloud.let/classes.dex):')
                url = str(input())
            print('Enter the drone id to send the command to:')
            drone = str(input())
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
            input_frame.payloads.append(bytes('Message to CNC', 'utf-8'))

            extras = cnc_pb2.Extras()
            extras.commander_id = self.id
            extras.cmd.for_drone_id = drone
            if selection == 1:
                extras.cmd.halt = True
            elif selection == 2:
                extras.cmd.script_url = url

            input_frame.extras.Pack(extras)
            
            logger.debug(f"Sending message #{self.frames_processed}...")
            return input_frame

        return [
            ProducerWrapper(producer=producer, source_name=self._source_name)
        ]

    def consumer(self, result_wrapper):
        logger.debug(f"Received results for frame {self.frames_processed}.")
        if len(result_wrapper.results) != 1:
            logger.error('Got %d results from server',
                            len(result_wrapper.results))
            return

        result = result_wrapper.results[0]
        if result.payload_type != gabriel_pb2.PayloadType.TEXT:
            type_name = gabriel_pb2.PayloadType.Name(result.payload_type)
            logger.error('Got result of type %s', type_name)
            return
        self.frames_processed += 1            
        logger.info(result.payload.decode('utf-8'))
        