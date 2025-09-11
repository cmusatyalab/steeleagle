#!/usr/bin/env python3

# Copyright (C) 2024 Carnegie Mellon University
# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import argparse
import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from urllib.parse import urlparse
from zipfile import ZipFile

import aiofiles
import aiohttp
import redis
import zmq
import zmq.asyncio
from google.protobuf import text_format
from google.protobuf.message import DecodeError
from util.utils import setup_logging

from bindings.python.services import remote_service_pb2, control_service_pb2, mission_service_pb2

logger = logging.getLogger(__name__)

class SwarmController:
    '''
    Multiplexes requests from connected commanders to target vehicles. Also handles
    messages sent between vehicles.
    '''
    def __init__(
        self, alt, compiler_file, red, request_sock, router_sock, spacing, angle
    ):
        self.alt = alt
        self.compiler_file = compiler_file
        self.request_sock = request_sock
        self.router_sock = router_sock
        self.running = True
        self.patrol_area_list = None
        self.mission_supervisor = MissionSupervisor(self.router_sock)
        self.spacing = spacing
        self.angle = angle

        if not os.path.exists(out_dir):
            os.makedir(out_dir)

    async def run(self):
        await asyncio.gather(self.listen_cmdrs())

    async def compile_mission(self, dsl_file, kml_file):
        pass

    async def send_to_drone(self, req, base_url, drone_list):
        try:
            # Send the command to each drone
            logger.info(f"Sending request {req.seq_num} to drones...")

            for drone_id in drone_list:
                await self.router_sock.send_multipart(
                    [drone_id.encode("utf-8"), req.SerializeToString()]
                )
                logger.info(f"Delivered request to drone {drone_id}.")
        except Exception as e:
            logger.error(f"Error sending request to drone: {e}")

    async def listen_cmdrs(self):
        while self.running:
            # Listen for incoming requests from cmdr
            msg = await self.request_sock.recv()
            try:
                req = controlplane.Request()
                req.ParseFromString(msg)
                logger.info(f"Request received:\n{text_format.MessageToString(req)}")
            except DecodeError:
                await self.request_sock.send(
                    b"Error decoding protobuf. Did you send a controlplane_pb2?"
                )
                logger.info("Error decoding protobuf. Did you send a controlplane_pb2?")
                continue

            # get the drone list
            if req.HasField("veh"):
                drone_list = list(
                    req.veh.drone_ids
                )  # convert from protobuf list to python list to support index() syntax
            else:
                drone_list = list(req.msn.drone_ids)
            logger.info(f"drone list: {drone_list}")

            # Check if the command contains a mission and compile it if true
            base_url = None
            if req.msn.action == controlplane.MissionAction.DOWNLOAD:
                # Cancel the existing mission, if applicable
                if self.mission_supervisor.get_mission() is not None:
                    await self.mission_supervisor.stop_mission_supervision()

                # download the script
                script_url = req.msn.url
                logger.info(f"script url: {script_url}")
                dsl, kml = await SwarmController.download_script(script_url)

                # compile the mission
                try:
                    await self.compile_mission(dsl, kml)
                except Exception as e:
                    logger.error(f"Compiler received error {e}")
                    await self.request_sock.send(b"ACK")
                    continue

                patrol_area_list = await PatrolArea.load_from_file(self.waypoint_file)

                mission = StaticPatrolMission(drone_list, patrol_area_list, self.alt)
                await self.mission_supervisor.supervise(mission, drone_list)

                # get the base url
                parsed_url = urlparse(script_url)
                base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

            # send the command to the drone
            await self.send_to_drone(req, base_url, drone_list)
            await self.request_sock.send(b"ACK")
            logger.info("Sent ACK to commander")


async def main():
    setup_logging(logger)
    logger.setLevel(logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--droneport",
        type=int,
        default=5003,
        help="Specify port to listen for drone requests [default: 5003]",
    )
    parser.add_argument(
        "-c",
        "--cmdrport",
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
    parser.add_argument(
        "--altitude", type=int, default=15, help="base altitude for the drones mission"
    )
    parser.add_argument(
        "--compiler_file", default="../../../sdk/dsl/", help="compiler file name"
    )
    parser.add_argument(
        "--spacing", type=int, default=18, help="Spacing for corridor scan"
    )
    parser.add_argument(
        "--angle", type=int, default=100, help="Spacing for corridor scan"
    )
    args = parser.parse_args()

    # Set the altitude
    alt = args.altitude
    logger.info(f"Starting control plane with altitude {alt}...")

    spacing = args.spacing
    logger.info(f"Starting control plane with {spacing=}...")

    angle = args.angle
    logger.info(f"Starting control plane with {angle=}...")

    compiler_file = args.compiler_file
    logger.info(f"Using compiler file: {compiler_file}")

    # Connect to redis
    red = redis.Redis(
        host="redis",
        port=args.redis,
        username="steeleagle",
        password=f"{args.auth}",
        decode_responses=True,
    )
    logger.info(f"Connected to redis on port {args.redis}...")

    # Set up the commander socket
    ctx = zmq.asyncio.Context()
    request_sock = ctx.socket(zmq.REP)
    request_sock.bind(f"tcp://*:{args.cmdrport}")
    logger.info(f"Listening on tcp://*:{args.cmdrport} for commander requests...")

    # Set up the drone socket
    async_ctx = zmq.asyncio.Context()
    router_sock = async_ctx.socket(zmq.ROUTER)
    router_sock.setsockopt(zmq.ROUTER_HANDOVER, 1)
    router_sock.bind(f"tcp://*:{args.droneport}")
    logger.info(f"Listening on tcp://*:{args.droneport} for drone connections...")

    controller = SwarmController(
        alt, compiler_file, red, request_sock, router_sock, spacing, angle
    )
    try:
        await controller.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
