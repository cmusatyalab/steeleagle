#!/usr/bin/env python3

# Copyright 2022 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import os
import numpy as np
from gabriel_protocol import gabriel_pb2
from gabriel_client.websocket_client import ProducerWrapper
import logging
from cnc_protocol import cnc_pb2
import asyncio
from PIL import Image
import cv2

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class TextCommanderAdapter:
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
            print('0. Get drone list')
            print('1. Get drone list (plus stream from drone)')
            print('2. Halt (killswitch)')
            print('3. Send Script URL')
            print('Enter the number of the command you wish to send:')
            selection = int(input())
            if selection == 2:
                print('Enter the URL where the script resides (i.e http://cloud.let/classes.dex):')
                url = str(input())
            if selection > 0:
                print('Enter the drone id to send the command to:')
                drone = str(input())
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
            input_frame.payloads.append(bytes('Message to CNC', 'utf-8'))

            extras = cnc_pb2.Extras()
            extras.commander_id = self.id
            if selection != 0:
                extras.cmd.for_drone_id = drone
                if selection == 2:
                    extras.cmd.halt = True
                elif selection == 3:
                    extras.cmd.script_url = url

            input_frame.extras.Pack(extras)
            
            logger.debug(f"Sending message #{self.frames_processed}...")
            return input_frame

        return [
            ProducerWrapper(producer=producer, source_name=self._source_name)
        ]

    def consumer(self, result_wrapper):
        logger.debug(f"Received results for frame {self.frames_processed}.")
        if len(result_wrapper.results) < 1 or len(result_wrapper.results)> 2:
            logger.error('Got %d results from server',
                            len(result_wrapper.results))
            return

        result = result_wrapper.results[0]
        if result.payload_type != gabriel_pb2.PayloadType.TEXT:
            type_name = gabriel_pb2.PayloadType.Name(result.payload_type)
            logger.error('Got result of type %s', type_name)
            return
        try:

            self.frames_processed += 1
            logger.info(result.payload.decode('utf-8'))
            if len(result_wrapper.results) == 2:
                np_data = np.fromstring(result_wrapper.results[1].payload, dtype=np.uint8)
                img = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                i = Image.fromarray(img)
                i.show('Stream')

        except Exception as e:
            logger.error(e)
        
