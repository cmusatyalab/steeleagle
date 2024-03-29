#!/usr/bin/env python3

# Copyright 2022 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import os
import asyncio
import numpy as np
from gabriel_protocol import gabriel_pb2
from gabriel_client.websocket_client import ProducerWrapper
import logging
from cnc_protocol import cnc_pb2, openscout_pb2
import random
import time
import cv2
import uuid

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class DroneAdapter:
    def __init__(self, preprocess, source_name, drone_id):
        '''
        preprocess should take one frame parameter
        produce_engine_fields takes no parameters
        consume_frame should take one frame parameter and one engine_fields
        parameter
        '''
        self.drone_id = drone_id
        self._preprocess = preprocess
        self._source_name = source_name
        self.frames_processed = 0

    def produce_openscout_extras(self):
        extras = openscout_pb2.Extras()
        extras.client_id = str(uuid.uuid4())
        extras.location.latitude = 40.41348 - random.uniform(0.01, 0.05)
        extras.location.longitude = -79.94964 + random.uniform(0.01, 0.05)
        extras.location.name = os.uname().nodename
        return extras

    def produce_cnc_extras(self):
        extras = cnc_pb2.Extras()
        extras.drone_id = self.drone_id
        extras.location.latitude = 40.41348 - random.uniform(0.01, 0.05)
        extras.location.longitude = -79.94964 + random.uniform(0.01, 0.05)
        extras.location.name = os.uname().nodename
        if self.frames_processed == 0:
            extras.registering = True
        return extras

    def get_producer_wrappers(self):
        async def producer():
            await asyncio.sleep(3)
            input_frame = gabriel_pb2.InputFrame()

            input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
            input_frame.payloads.append(bytes('Message to CNC', 'utf-8'))
            extras = self.produce_cnc_extras()
            if extras is not None:
                input_frame.extras.Pack(extras)


            logger.debug(f"Sending message #{self.frames_processed}...")
            return input_frame

        return [
            ProducerWrapper(producer=producer, source_name=self._source_name)
        ]

    def consumer(self, result_wrapper):
        logger.debug(f"Received results for frame {self.frames_processed}.")
        if len(result_wrapper.results) != 1:
            logger.debug('Got %d results from server',
                         len(result_wrapper.results))
            return
        result = result_wrapper.results[0]
        if result.payload_type != gabriel_pb2.PayloadType.TEXT:
            type_name = gabriel_pb2.PayloadType.Name(result.payload_type)
            logger.error('Got result of type %s', type_name)
            return
        self.frames_processed += 1
        extras = cnc_pb2.Extras()
        result_wrapper.extras.Unpack(extras)
        logger.info(extras)
        if extras.cmd.halt:
            logger.info(result.payload.decode('utf-8'))
        elif extras.cmd.script_url != '':
            logger.info(
                f"{result.payload.decode('utf-8')} {extras.cmd.script_url}")
