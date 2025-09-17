#!/usr/bin/env python3

# Copyright (C) 2024 Carnegie Mellon University
# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import argparse
import json
import logging
import os
import zmq
import zmq.asyncio
import aiorwlock
from google.protobuf import text_format
from google.protobuf.message import DecodeError
from util.utils import setup_logging
from steeleagle_sdk.protocol.services.remote_service_pb2 import CommandResponse
from steeleagle_sdk.protocol.services.remote_service_pb2_grpc import RemoteServicer

logger = logging.getLogger(__name__)

class SwarmController(RemoteServicer):
    '''
    Multiplexes requests from connected commanders to target vehicles. Also handles
    messages sent between vehicles.
    '''
    def __init__(self, _router_sock):
        self.__router_sock = _router_sock
        self._sequence_number_lock = asyncio.Lock()
        self._sequence_number = 0
        self._response_map_lock = aiorwlock.RWLock()
        self._response_map = {}

    async def _get_sequence_number(self):
        '''
        Gets the current sequence number, then increases it.
        '''
        async with self._sequence_number_lock:
            new_sequence_number = self._sequence_number
            self._sequence_number += 1
            return new_sequence_number

    async def _poll_for_response(self, sequence_number):
        '''
        Check to see if a response has been received for a RemoteControl request.
        '''
        async with self._response_map_lock.reader_lock():
            return self.response_map[sequence_number] if sequence_number in self.response_map \
                else None
    
    async def Command(self, request, context):
        '''
        Implementation of RPC Command method defined in the SDK.
        '''
        try:
            yield generate_response(0)
            request.sequence_number = await self._get_sequence_number()
            await self._router_sock.send_multipart(
                [request.vehicle_id.encode("utf-8"), request.SerializeToString()]
            )
            response = None
            while not response and context.is_active():
                yield generate_response(1) 
                await asyncio.sleep(1)
                response = await self._poll_for_response(request.sequence_number):
            yield response if response else generate_response(3)
        except Exception as e:
            logger.error(f"Error sending request to vehicle: {e}")
            yield generate_response(4)

    async def _listen_for_responses(self):
        try:
            while True:
                data = await self._router_sock.recv()
                # Parse the raw data into a response
                response = CommandResponse()
                response.ParseFromString(data)
                async with self._response_map_lock.writer_lock():
                    self._response_map[response.sequence_number] = response.response
        except asyncio.exceptions.CancelledError:
            return


async def main():
    setup_logging(logger)
    logger.setLevel(logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--rc_port",
        type=int,
        default=5003,
        help="Specify port to listen for vehicle connections [default: 5003]",
    )
    parser.add_argument(
        "-c",
        "--commander_port",
        type=int,
        default=6001,
        help="Specify port to listen for commander requests [default: 6001]",
    )
    parser.add_argument(
        "-r",
        "--redis",
        type=int,
        default=6379,
        help="Set port number for redis connection [default: 6379]",
    )
    parser.add_argument("-a", "--auth", default="", help="Shared key for redis user.")
    args = parser.parse_args()

    compiler_file = args.compiler_file
    logger.info(f"Using compiler directory: {compiler_dir}")

    # Connect to redis
    red = redis.Redis(
        host="redis",
        port=args.redis,
        username="steeleagle",
        password=f"{args.auth}",
        decode_responses=True,
    )
    logger.info(f"Connected to redis on port {args.redis}...")
    
    # Set up the vehicle socket
    ctx = zmq.asyncio.Context()
    router_sock = ctx.socket(zmq.ROUTER)
    router_sock.setsockopt(zmq.ROUTER_HANDOVER, 1)
    router_sock.bind(f"tcp://*:{args.rc_port}")
    logger.info(f"Listening on tcp://*:{args.rc_port} for vehicle connections...")

    controller = SwarmController(router_sock)
    try:
        await controller.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
