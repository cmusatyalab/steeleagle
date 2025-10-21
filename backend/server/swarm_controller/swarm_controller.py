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
import time
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

import airspace_control.airspace_control_engine as acs
import protocol.common_pb2 as common
import protocol.controlplane_pb2 as controlplane

logger = logging.getLogger(__name__)


class PatrolArea:
    """Represents an area for patrolling."""

    def __init__(self, name):
        # The name of this patrol area
        self.name = name
        # The patrol waypoints that are part of this patrol area. Each item
        # in this list constitutes a segment of this patrol.
        self.patrol_waypoints = []

        self.partitions = []
        # Each iterator in this list contains the waypoints assigned to
        # a drone.
        self.waypoint_iters = None

    def get_patrol_waypoints(self):
        return self.patrol_waypoints

    def get_partition(self, drone_idx):
        return self.partitions[drone_idx]

    def get_name(self):
        return self.name

    def __repr__(self):
        return str(self.patrol_waypoints)

    def add_patrol_waypoints(self, waypoints):
        """Add a waypoint pair as a part of this patrol area."""
        self.patrol_waypoints.append(waypoints)

    def update_unpatrolled_lines(self):
        """
        Stores the patrol lines that have not yet been patrolled by a drone,
        discarding the rest.
        """
        if self.waypoint_iters is None:
            return
        self.patrol_waypoints = []
        for it in self.waypoint_iters:
            for line in it:
                self.patrol_waypoints.append(line)

    def create_partitioning(self, num_drones):
        """
        Create an assignment from drones to patrol lines.
        """
        # Figure out which patrol lines are still pending
        self.update_unpatrolled_lines()
        num_lines = len(self.patrol_waypoints)

        self.waypoint_iters = []
        logger.info("Creating partition iters")

        if num_drones >= num_lines:
            logger.info(
                f"{num_lines=} {num_drones=}. Assigning 1 patrol line per drone"
            )
            for i in range(num_drones):
                partition = []
                if i < num_lines:
                    partition = [self.patrol_waypoints[i]]
                self.waypoint_iters.append(iter(partition))
                self.partitions.append(partition)
            return

        lines_per_drone = num_lines // num_drones
        logger.info(
            f"{num_lines=} {num_drones=}. Assigning {lines_per_drone} patrol lines per drone"
        )

        for i in range(num_drones - 1):
            partition = self.patrol_waypoints[
                i * lines_per_drone : (i + 1) * lines_per_drone
            ]
            self.waypoint_iters.append(iter(partition))
            self.partitions.append(partition)

        # Assign remaining patrol lines to the last drone
        partition = self.patrol_waypoints[(num_drones - 1) * lines_per_drone :]
        self.waypoint_iters.append(iter(partition))
        self.partitions.append(partition)

    def get_patrol_line(self, drone_idx):
        try:
            return next(self.waypoint_iters[drone_idx])
        except StopIteration:
            # Steal a patrol line from another drone
            for i in range(0, len(self.waypoint_iters)):
                if i == drone_idx:
                    continue
                try:
                    return next(self.waypoint_iters[i])
                except StopIteration:
                    continue
        return None

    @staticmethod
    async def load_from_file(filename):
        async with aiofiles.open(filename) as f:
            contents = await f.read()
        data = json.loads(contents)

        patrol_area_list = []

        for patrol_name, sub_patrols in data.items():
            patrol_area = PatrolArea(patrol_name)
            patrol_area_list.append(patrol_area)
            for sub_patrol_name, sub_patrol_waypoints in sub_patrols.items():
                waypoints = PatrolWaypoints(patrol_name + "." + sub_patrol_name)
                patrol_area.add_patrol_waypoints(waypoints)

        return patrol_area_list


@dataclass
class PatrolWaypoints:
    """Represents the waypoints for a patrolling line segment."""

    waypoints: str

    def __repr__(self):
        return self.waypoints


@dataclass
class PatrolMissionState:
    drone_list: list[str]
    patrol_area_list: list[PatrolArea]
    current_patrol_area: PatrolArea
    patrol_area_iter: Iterator[list[PatrolArea]]
    drone_altitudes: list[int]


class Mission(ABC):
    def __init__(self, state):
        self.state = state

    def get_state(self):
        return self.state

    @abstractmethod
    def state_transition(self, drone_id, msg):
        pass

    @abstractmethod
    def update_drone_list(self, drone_list):
        pass


class StaticPatrolMission(Mission):
    DRONE_ALTITUDE_SEP = 3

    def __init__(self, drone_list, patrol_area_list, alt):
        # Set the altitude for each drone
        state = PatrolMissionState(drone_list, patrol_area_list, None, None, None)
        super().__init__(state)
        self.state.patrol_area_iter = iter(patrol_area_list)
        self.state.current_patrol_area = next(self.state.patrol_area_iter)
        self._create_partitioning()

        self.state.drone_altitudes = [
            alt + self.DRONE_ALTITUDE_SEP * i for i in range(len(drone_list))
        ]

    def __repr__(self):
        return str(self.state)

    def advance_patrol_area(self):
        self.state.current_patrol_area = next(self.state.patrol_area_iter)
        self._create_partitioning()

    def state_transition(self, drone_id, rep):
        logger.debug(f"Started state transition for drone {drone_id}, {rep=}")
        drone_idx = self.state.drone_list.index(drone_id)

        req = controlplane.Request()
        req.msn.action = controlplane.MissionAction.PATROL
        req.seq_num = rep.seq_num

        if rep.resp == common.ResponseStatus.COMPLETED:
            try:
                self.advance_patrol_area()
            except StopIteration:
                logger.info(
                    f"Drone {drone_id}: PatrolArea finished (StopIteration). Sending FINISH status."
                )
                logger.info(f"{common.PatrolStatus.FINISH}")
                req.msn.patrol_area.status = common.PatrolStatus.FINISH
                return (drone_id, req)
            except Exception as e:
                logger.error(
                    f"Unexpected error during advance_patrol_area for drone {drone_id}: {e}",
                    exc_info=True,
                )

        partitioned_areas = self.state.current_patrol_area.get_partition(drone_idx)
        logger.info(f"{partitioned_areas=}")
        altitude = self.state.drone_altitudes[drone_idx]
        logger.info(f"Drone {drone_id} is at altitude {altitude}")
        logger.info(f"Drone {drone_id} is assigned to patrol area {partitioned_areas}")

        req.msn.patrol_area.status = common.PatrolStatus.CONTINUE
        req.msn.patrol_area.areas.extend([p.waypoints for p in partitioned_areas])
        req.msn.patrol_area.altitude = self.state.drone_altitudes[drone_idx]

        return (drone_id, req)

    def update_drone_list(self, drone_list):
        self.state.drone_list = drone_list
        self._create_partitioning()

    def _create_partitioning(self):
        num_drones = len(self.state.drone_list)
        self.state.current_patrol_area.create_partitioning(num_drones)


class MissionSupervisor:
    def __init__(self, router_sock):
        self.mission = None
        self.router_sock = router_sock

    def get_mission(self):
        return self.mission

    async def send_drone_msg(self, drone_id, request):
        logger.info(f"Sending message {request} to {drone_id}")
        await self.router_sock.send_multipart(
            [drone_id.encode("utf-8"), request.SerializeToString()]
        )

    async def drone_handler(self):
        while True:
            # Listen for mission updates from drones
            drone_id, rep = await self.listen_drones()
            drone_id, drone_msg = self.mission.state_transition(drone_id, rep)

            # Send mission updates to drones
            await self.send_drone_msg(drone_id, drone_msg)

    async def supervise(self, mission, drone_list):
        self.mission = mission
        self.drone_handler_task = asyncio.create_task(self.drone_handler())
        self.drone_list = drone_list

    async def stop_mission_supervision(self):
        self.mission = None
        self.drone_list = []
        self.drone_handler_task.cancel()

    async def listen_drones(self):
        identity, msg = await self.router_sock.recv_multipart()
        rep = controlplane.Response()
        rep.ParseFromString(msg)
        logger.info(f"Received msg from {identity=}: {rep=}")
        drone_id = identity.decode("utf-8")
        return drone_id, rep


class SwarmController:
    # Set up the paths and variables for the compiler
    compiler_path = "/compiler"
    output_path = "/compiler/out/flightplan"
    platform_path = "/dsl/python/project"
    waypoint_file = "/compiler/out/waypoint.json"

    def __init__(
        self, alt, compiler_file, red, request_sock, router_sock, spacing, angle, air_control
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
        self.air_control = air_control

        out_dir = "/compiler/out"
        if not os.path.exists(out_dir):
            os.mkdir(out_dir)

    async def run(self):
        await asyncio.gather(self.listen_cmdrs(), self.operate_airspace_control())

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
    
    async def operate_airspace_control(self):
        update_rate = .25
        drone_refresh_rate = 1
        drone_list = []
        for drone_id in self.red.keys():
            drone_list.append(drone_id)
        drone_check_time = time.time()
        while self.running:
            # clear and refresh drone list periodically
            start_t = time.time()
            if start_t - drone_check_time >= drone_refresh_rate:
                drone_list = []
                for drone_id in self.red.keys("drone:"):
                    drone_list.append(drone_id.split("drone:")[-1])
            for drone_id in drone_list:
                result = self.red.xread(streams={f"telemetry:{drone_id}": '$'}, count=1)
                for stream_name, message in result:
                    for message_id, message_data in message:
                        curr_pos = (message_data['latitude'], message_data['longitude'], message_data['rel_altitude'])
                        curr_vel = (message_data['v_body_forward'], message_data['v_body_lateral'], message_data['v_body_altitude'])
                        if not self.air_control.validate_position(drone_id, curr_pos[0], curr_pos[1], curr_pos[2]):
                            req = controlplane.Request()
                            req.seq_num = int(time.time())
                            req.timestamp.GetCurrentTime()
                            req.msn.drone_ids.append(drone_id)
                            req.msn.action = controlplane.MissionAction.STOP
                            logger.info(f"Airspace violation reported. Directing drone {drone_id} to halt...")
                            await self.router_sock.send_multipart([drone_id.encode("utf-8"), req.SerializeToString()])
                            logger.info(f"Airspace violation follow-up. Kill signal sent to drone {drone_id}")
            await asyncio.sleep(max(0.01, update_rate - (time.time() - start_t)))


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
    parser.add_argument(
        "--lat_start", type=float, default=40.410411, help="south-most latitude for airspace management"
    )
    parser.add_argument(
        "--lat_end", type=float, default=40.414100, help="north-most latitude for airspace management"
    )
    parser.add_argument(
        "--lat_parts", type=int, default=40, help="number of latitudinal slices for airspace partitioning"
    )
    parser.add_argument(
        "--lon_start", type=float, default=-79.949735, help="west-most longitude for airspace management"
    )
    parser.add_argument(
        "--lon_end", type=float, default=-79.946752, help="east-most longitude for airspace management"
    )
    parser.add_argument(
        "--lon_parts", type=int, default=25, help="number of longitudinal slices for airspace partitioning"
    )
    parser.add_argument(
        "--alt_floor", type=int, default=0, help="lowest relative altitude for airspace management"
    )
    parser.add_argument(
        "--alt_ceil", type=int, default=400, help="highest relative altitude for airspace management"
    )
    parser.add_argument(
        "--alt_parts", type=int, default=4, help="number of lateral slices by altitude for airspace partitioning"
    )
    parser.add_argument(
        "--nofly_left", type=float, default=-79.947750, help="west bound of nofly zone for integration testing"
    )
    parser.add_argument(
        "--nofly_right", type=float, default= -79.947000, help="east bound of nofly zone for integration testing"
    )
    parser.add_argument(
        "--nofly_up", type=float, default=40.413500, help="north bound of nofly zone for integration testing"
    )
    parser.add_argument(
        "--nofly_down", type=float, default=40.413000, help="south bound of nofly zone for integration testing"
    )
    parser.add_argument(
        "--nofly_floor", type=int, default=0, help="lower bound of nofly zone for integration testing"
    )
    parser.add_argument(
        "--nofly_ceiling", type=int, default=99, help="upper bound of nofly zone for integration testing"
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

    # Set up airspace control engine
    lat_start = args.lat_start
    lat_end = args.lat_end
    lon_start = args.lon_start
    lon_end = args.lon_end
    corners = [(lat_end, lon_start), (lat_start, lon_start), (lat_start, lon_end), (lat_end, lon_end)]
    air_controller = acs.AirspaceControlEngine(corners, args.lat_parts, args.lon_parts, args.alt_parts,
                                               args.alt_start, args.alt_end)
    air_controller.mark_no_fly_scan(args.nofly_left, args.nofly_right, args.nofly_up, args.nofly_down,
                               args.nofly_floor, args.nofly_ceiling)

    controller = SwarmController(
        alt, compiler_file, red, request_sock, router_sock, spacing, angle, air_controller
    )
    try:
        await controller.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    asyncio.run(main())
