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
from google.protobuf import text_format
from google.protobuf.message import DecodeError
from util.utils import setup_logging

from steeleagle_sdk.protocol.services.remote_service_pb2_grpc import RemoteServicer
from steeleagle_sdk.dsl.compiler import compile_dsl

logger = logging.getLogger(__name__)

class SwarmController(RemoteServicer):
    '''
    Multiplexes requests from connected commanders to target vehicles. Also handles
    messages sent between vehicles.
    '''
    def __init__(self, _router_sock):
        self.__router_sock = _router_sock
        self._response_map = {}

    async def _send_to_vehicle(self, req, vehicle_list):
        '''
        Relay remote control commands to the listed vehicles.
        '''
        try:
            for vehicle_id in vehicle_list:
                await self._router_sock.send_multipart(
                    [vehicle_id.encode("utf-8"), req.SerializeToString()]
                )
                logger.info(f"Delivered request to vehicle {vehicle_id}.")
        except Exception as e:
            logger.error(f"Error sending request to vehicle: {e}")

    def _poll_for_response(self, sequence_number):
        '''
        Check to see if a response has been received for a RemoteControl requuest.
        '''
        return self.response_map[sequence_number] if sequence_number in self.response_map \
                else None
    
    async def Command(self, request, context):
        '''
        Implementation of RPC Command method defined in the SDK.
        '''


    async def Compile(self, request, context):
        '''
        Implementation of RPC CompileDSL method defined in the SDK.
        '''


    async def listen_for_commands(self):
        sequence_number = 0
        while self.running:
            # Listen for incoming requests from cmdr
            msg = await self.request_sock.recv()
            try:
                req = remote_service_pb2.RemoteControlRequest()
                req.ParseFromString(msg)
                req.sequence_number = sequence_number
                sequence_number += 1
                logger.info(f"Request received:\n{text_format.MessageToString(req)}")
            except DecodeError:
                await self.request_sock.send(
                    b"Error decoding protobuf. Did you send a RemoteControlRequest?"
                )
                logger.info("Error decoding protobuf. Did you send a RemoteControlRequest?")
                continue

            # send the command to the vehicle
            await self.send_to_vehicle(req, base_url, vehicle_list)
            await self.request_sock.send(b"ACK")


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
    
    ctx = zmq.asyncio.Context()

    # Set up the commander socket
    request_sock = ctx.socket(zmq.ROUTER)
    request_sock.setsockopt(zmq.ROUTER_HANDOVER, 1)
    request_sock.bind(f"tcp://*:{args.cmdrport}")
    logger.info(f"Listening on tcp://*:{args.commander_port} for commander requests...")

    # Set up the vehicle socket
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
