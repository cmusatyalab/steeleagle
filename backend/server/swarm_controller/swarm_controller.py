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

import protocol.common_pb2 as common
import protocol.controlplane_pb2 as controlplane

logger = logging.getLogger(__name__)

class SwarmController:
    # Set up the paths and variables for the compiler
    compiler_path = "/compiler"
    output_path = "/compiler/out/flightplan"
    platform_path = "/dsl/python/project"
    waypoint_file = "/compiler/out/waypoint.json"

    def __init__(
        self, alt, compiler_file, red, request_sock, router_sock, spacing, angle
    ):
        self.alt = alt
        self.compiler_file = compiler_file
        self.red = red
        self.request_sock = request_sock
        self.router_sock = router_sock
        self.running = True
        self.patrol_area_list = None
        self.mission_supervisor = MissionSupervisor(self.router_sock)
        self.spacing = spacing
        self.angle = angle

        out_dir = "/compiler/out"
        if not os.path.exists(out_dir):
            os.makedir(out_dir)

    async def run(self):
        await asyncio.gather(self.listen_cmdrs())

    @staticmethod
    async def download_file(script_url, filename):
        async with aiohttp.ClientSession() as session:
            async with session.get(script_url) as resp:
                resp.raise_for_status()
                async with aiofiles.open(filename, mode="wb") as f:
                    async for chunk in resp.content.iter_chunked(8192):
                        await f.write(chunk)

    @staticmethod
    async def extract_zip(filename):
        def _extract():
            dsl_file = kml_file = None
            with ZipFile(filename, "r") as z:
                z.extractall(path=SwarmController.compiler_path)
                for file_name in z.namelist():
                    if file_name.endswith(".dsl"):
                        dsl_file = file_name
                    elif file_name.endswith(".kml"):
                        kml_file = file_name
            return dsl_file, kml_file

        return await asyncio.to_thread(_extract)

    @staticmethod
    async def download_script(script_url):
        try:
            # Get the ZIP file name from the URL
            filename = script_url.rsplit(sep="/")[-1]
            logger.info(f"Writing {filename} to disk...")

            # Download the ZIP file
            await SwarmController.download_file(script_url, filename)

            # Extract all contents of the ZIP file and remember .dsl and .kml filenames
            dsl_file, kml_file = await SwarmController.extract_zip(filename)

            # Log or return the results
            logger.info(f"Extracted files: {dsl_file} {kml_file}")

            return dsl_file, kml_file

        except Exception as e:
            logger.error(f"Error during download or extraction: {e}")

    async def compile_mission(self, dsl_file, kml_file):
        # Construct the full paths for the DSL and KML files
        dsl_file_path = os.path.join(self.compiler_path, dsl_file)
        kml_file_path = os.path.join(self.compiler_path, kml_file)
        jar_path = os.path.join(self.compiler_path, self.compiler_file)
        altitude = str(self.alt)

        # Define the command and arguments
        command = [
            "java",
            "-jar",
            jar_path,
            "-o",
            self.output_path,
            "-l",
            self.platform_path,
            "-k",
            kml_file_path,
            "-s",
            dsl_file_path,
            "-p",
            "corridor",
            "--angle",
            str(self.angle),
            "--spacing",
            str(self.spacing),
            "-w",
            self.waypoint_file,
        ]

        # Run the command
        logger.info(f"Running command: {' '.join(command)}")

        proc = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )

        stdout, _ = await proc.communicate()

        if proc.returncode != 0:
            raise Exception(f"Mission compilation failed: {stdout.decode()}")

        # Log the output
        logger.info(f"Compilation output: {stdout.decode()}")

        # Output the results
        logger.info("Compilation successful.")

    async def send_to_drone(self, req, base_url, drone_list):
        try:
            logger.info(f"Sending request {req.seq_num} to drones...")
            # Send the command to each drone

            for drone_id in drone_list:
                # check if the cmd is a mission
                if base_url:
                    # reconstruct the script url with the correct compiler output path
                    req.msn.url = f"{base_url}{self.output_path}.ms"
                    logger.info(f"Drone-specific script url: {req.msn.url}")

                # send the command to the drone
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
        "--compiler_file", default="compile-2.0-full.jar", help="compiler file name"
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
