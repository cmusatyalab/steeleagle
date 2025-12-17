#!/usr/bin/env python3

# Copyright (C) 2024 Carnegie Mellon University
# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import argparse
import asyncio
import json
import redis
import zmq
import zmq.asyncio
import grpc
from concurrent import futures
import aiorwlock
# Protocol imports
from steeleagle_sdk.protocol.services.remote_service_pb2 import CompileMissionResponse, CommandResponse
from steeleagle_sdk.protocol.services.remote_service_pb2_grpc import RemoteServicer, add_RemoteServicer_to_server
from steeleagle_sdk.protocol.rpc_helpers import generate_response
from steeleagle_sdk.dsl import build_mission
from dataclasses import asdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SwarmController(RemoteServicer):
    '''
    Multiplexes requests from connected commanders to target vehicles. Also handles
    messages sent between vehicles.
    '''
    def __init__(self, _router_sock):
        self._router_sock: zmq.Socket = _router_sock
        self._sequence_number_lock = asyncio.Lock()
        self._sequence_number = 0
        self._response_map_lock = aiorwlock.RWLock()
        self._response_map = {}
        self.listener_task = asyncio.create_task(self._listen_for_responses())
        logger.info("SwarmController initialized.") 
        
    ######################### Mission #########################
    async def CompileMission(self, compile_request, context):
        dsl = compile_request.dsl_content
        mission = build_mission(dsl)
        logger.info(f"Built mission: {mission}")
        mission_json_text = json.dumps(asdict(mission))
        response = CompileMissionResponse(
            compiled_dsl_content=mission_json_text,
            response=generate_response(2)
        )
        yield response

    ######################### Control #########################
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
        async with self._response_map_lock.reader_lock:
            return self._response_map[sequence_number] if sequence_number in self._response_map \
                else None
    
    async def Command(self, request, context):
        '''
        Implementation of RPC Command method defined in the SDK.
        '''
        try:
            yield generate_response(0)
            request.sequence_number = await self._get_sequence_number()
            request.identity = 'server'
            await self._router_sock.send_multipart(
                [request.vehicle_id.encode("utf-8"), request.SerializeToString()]
            )
            response = None
            while not response:
                yield generate_response(1) 
                await asyncio.sleep(1)
                response = await self._poll_for_response(request.sequence_number)
            yield response if response else generate_response(3)
        except Exception as e:
            logger.error(f"Error sending request to vehicle: {e}")
            yield generate_response(4)

    async def _listen_for_responses(self):
        try:
            logger.info("Starting listener for vehicle responses...")
            while True:
                logger.info("Listening for vehicle responses...")
                _, data = await self._router_sock.recv_multipart()
                # Parse the raw data into a response
                response = CommandResponse()
                try:
                    response.ParseFromString(data)
                except Exception as e:
                    logger.error(f"Failed to parse response from vehicle: {e}")
                    continue
                logger.info(f"Received response: {response}, seq_num: {response.sequence_number}")
                async with self._response_map_lock.writer_lock:
                    self._response_map[response.sequence_number] = response.response
        except asyncio.exceptions.CancelledError:
            return

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v",
        "--vehicle_port",
        type=int,
        default=5003,
        help="Specify port to listen for vehicle connections [default: 5003]",
    )
    parser.add_argument(
        "-c",
        "--commander_port",
        type=int,
        default=5004,
        help="Specify port to listen for commander connections [default: 5004]",
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
    router_sock.bind(f"tcp://*:{args.vehicle_port}")
    logger.info(f"Listening on tcp://*:{args.vehicle_port} for vehicle connections...")

    # Start the server
    server = grpc.aio.server(
            futures.ThreadPoolExecutor(max_workers=10)
            )
    sc = SwarmController(router_sock)
    add_RemoteServicer_to_server(sc, server)
    server.add_insecure_port(f'[::]:{args.commander_port}')
    logger.info(f"Listening on tcp//*:{args.commander_port} for commander connections...")
    await server.start()
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        await server.stop(1)
        sc.listener_task.cancel()
        await sc.listener_task
        logger.info("Shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
