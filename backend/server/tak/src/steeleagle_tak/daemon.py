# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: Apache-2.0

"""Redis Telemetry to Cursor on Target (CoT) Daemon.

This daemon subscribes to Redis telemetry streams from SteelEagle vehicles
and republishes the data as Cursor on Target (CoT) messages using PyTAK.

Usage:
    python -m steeleagle_tak.daemon
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import datetime
import logging
import math
import os
import xml.etree.ElementTree as ET
from abc import abstractmethod
from configparser import ConfigParser, SectionProxy
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import aiohttp
import pytak
import redis.asyncio as redis

if TYPE_CHECKING:
    import multiprocessing as mp

logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

ESTIMATED_DRONE_SIZE = 1.0  # meters


class _RXDrain(pytak.RXWorker):
    async def run_once(self) -> None:
        if self.reader:
            data = await self.readcot()
            if data:
                self._logger.debug("RX data: %s", data)


def estimate_gps_accuracy(satellites: int) -> dict[str, Any]:
    """Estimate GPS accuracy based on satellite count."""
    if satellites < 4:
        return {
            "status": "NO_FIX",
            "horizontal_error": 15.0,  # meters
            "vertical_error": 30.0,  # meters
            "hdop": 5.0,
        }
    if satellites < 6:
        return {
            "status": "WEAK_SIGNAL",
            "horizontal_error": 6.5,  # meters
            "vertical_error": 13.0,  # meters
            "hdop": 2.5,
        }
    if satellites < 8:
        return {
            "status": "MODERATE_ACCURACY",
            "horizontal_error": 2.0,  # meters
            "vertical_error": 4.0,  # meters
            "hdop": 1.2,
        }
    return {
        "status": "HIGH_ACCURACY",
        "horizontal_error": 1.0,  # meters
        "vertical_error": 2.0,  # meters
        "hdop": 0.6,
    }


class CotSerializer(pytak.QueueWorker):
    """Publish Cursor on Target events."""

    def __init__(
        self,
        queue: asyncio.Queue | mp.Queue,
        config: SectionProxy | dict,
        poll_interval: float,
    ) -> None:
        """Initialize the serializer.

        Args:
            queue: PyTAK event queue to send CoT events to
            config: Configuration with CoT settings
            poll_interval: How frequently self.run_once is called (seconds)
        """
        super().__init__(queue, config)

        self.poll_interval = poll_interval
        logger.info(f"Initialized with poll interval: {self.poll_interval}s")

    async def handle_data(self, data: bytes) -> None:
        """Handle pre-CoT data, serialize to CoT Event, then puts on queue.

        Args:
            data: XML bytes of CoT event to queue
        """
        await self.put_queue(data)

    async def run(self, _: int = -1) -> None:
        """Continuously poll for updates."""
        while True:
            try:
                await self.run_once()
            except Exception:
                logger.exception("Unexpected error")
            await asyncio.sleep(self.poll_interval)

    @abstractmethod
    async def run_once(self) -> None:
        """Poll for events."""


class TelemetryToCotSerializer(CotSerializer):
    """Converts Redis telemetry data to Cursor on Target events.

    Subscribes to Redis telemetry streams, generating CoT events for each
    vehicle's location updates.
    """

    def __init__(
        self,
        queue: asyncio.Queue | mp.Queue,
        config: SectionProxy | dict,
        redis_client: redis.Redis,
    ) -> None:
        """Initialize the serializer.

        Args:
            queue: PyTAK event queue to send CoT events to
            config: Configuration with Redis and CoT settings
            redis_client: Connected Redis client
        """
        poll_interval = float(config.get("POLL_INTERVAL", 1.0))
        super().__init__(queue, config, poll_interval)

        self.redis_client = redis_client
        self.stale_time = int(config.get("COT_STALE", 120))

    async def process_vehicle_telemetry(self, vehicle_name: str) -> None:
        """Process latest telemetry for a vehicle and generate CoT event.

        Args:
            vehicle_name: Name of the vehicle to query
        """
        try:
            # Get latest telemetry from Redis stream
            latest = await self.redis_client.xrevrange(
                f"telemetry:{vehicle_name}", "+", "-", 1
            )

            if not latest:
                logger.debug(f"No telemetry found for vehicle: {vehicle_name}")
                return

            # Extract the most recent telemetry entry
            _, telem = latest[0]

            # logger.debug("{}".format(telem))

            # Required fields for CoT
            lat = telem.get(b"latitude")
            lon = telem.get(b"longitude")

            if lat is None or lon is None:
                logger.warning(
                    f"Missing location data for {vehicle_name}: lat={lat}, lon={lon}"
                )
                return

            # Optional fields
            abs_alt = telem.get(b"abs_altitude", telem.get(b"rel_altitude", b"0"))

            # Error bounds
            # CoT uses object + estimated error so that it reports a cylinder space
            # in which the object is expected to be, which can then be used for
            # collision avoidance.

            drone_size = ESTIMATED_DRONE_SIZE

            # Estimate positioning error off of the number of visible satellites
            # (really should propagate any known errors along with telemetry data)
            satellites = int(telem.get(b"sats", 0))
            estimated = estimate_gps_accuracy(satellites)

            circular_error = drone_size + estimated["horizontal_error"]
            height_error = drone_size + estimated["vertical_error"]

            # Generate CoT event
            cot_xml = pytak.gen_cot_xml(
                lat=float(lat),
                lon=float(lon),
                hae=float(abs_alt),
                ce=circular_error,
                le=height_error,
                uid=f"steeleagle-{vehicle_name}",
                callsign=vehicle_name,
                cot_type="a-f-A-M-H-Q",
                stale=self.stale_time,
            )

            if cot_xml is None:
                logger.error(f"Failed to generate CoT XML for {vehicle_name}")
                return

            # Extend with additional QoS and tracking information

            cot_xml.set("qos", "1-r-c")  # frequent, low priority updates

            detail = cot_xml.find("detail")
            if detail is None:
                detail = ET.SubElement(cot_xml, "detail")

            takv = ET.Element("takv")
            takv.set("os", "Linux")
            takv.set("device", "Drone")
            takv.set("version", "1.0")
            takv.set("platform", "SteelEagle")
            detail.append(takv)

            bearing = telem.get(b"bearing")
            if bearing is not None:
                vel_x = float(telem.get(b"v_body_forward", 0.0))
                vel_y = float(telem.get(b"v_body_lateral", 0.0))
                vel_z = float(telem.get(b"v_body_altitude", 0.0))

                speed = math.sqrt(vel_x**2 + vel_y**2 + vel_z**2)
                vel_h = math.sqrt(vel_x**2 + vel_y**2)
                slope = math.degrees(math.atan2(vel_z, vel_h))

                track = ET.Element("track")
                track.set("course", str(int(bearing)))
                track.set("speed", str(speed))
                track.set("slope", str(slope))
                detail.append(track)

            battery = telem.get(b"battery")
            if battery is not None:
                status = ET.Element("status")
                status.set("battery", str(int(battery)))
                detail.append(status)

            # Add any other info as remarks
            additional = [
                f"satellites: {satellites}",
            ]
            remarks = ET.Element("remarks")
            remarks.text = " ".join(additional)
            detail.append(remarks)

            # Convert to bytes and queue
            event_xml = ET.tostring(cot_xml, encoding="utf-8")
            await self.handle_data(event_xml)

        except redis.RedisError:
            logger.exception(f"Redis error for {vehicle_name}")
        except Exception:
            logger.exception(f"Error processing {vehicle_name}")

    async def run_once(self) -> None:
        try:
            # Find all active vehicle telemetry streams
            telemetry_keys = await self.redis_client.keys("telemetry:*")

            for key in telemetry_keys:
                vehicle_name = key.decode("utf-8").split(":", 1)[1]
                await self.process_vehicle_telemetry(vehicle_name)

        except redis.RedisError:
            logger.exception("Redis connection error")


class DetectionToCotSerializer(CotSerializer):
    """Converts Redis detection data to Cursor on Target events.

    Subscribes to Redis detection sets, generating CoT events for detected
    objects.
    """

    def __init__(
        self,
        queue: asyncio.Queue | mp.Queue,
        config: SectionProxy | dict,
        redis_client: redis.Redis,
        http_session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the serializer.

        Args:
            queue: PyTAK event queue to send CoT events to
            config: Configuration with Redis and CoT settings
            redis_client: Connected Redis client
            http_session: aiohttp client session for fetching images
        """
        poll_interval = float(config.get("DETECTION_POLL_INTERVAL", "5.0"))
        super().__init__(queue, config, poll_interval)

        self.http_session = http_session
        self.redis_client = redis_client
        self.detection_ttl = int(config.get("DETECTION_TTL", "1200"))
        self._detected: dict[str, float] = {}

        detection_class_map = str(config.get("DETECTION_CLASS_MAP", ""))
        self.class_to_cot_map: dict[str, str] = {}
        if detection_class_map:
            for mapping in detection_class_map.split(","):
                parts = mapping.strip().split(":")
                if len(parts) == 2:
                    class_name, cot_type = parts
                    self.class_to_cot_map[class_name.strip()] = cot_type.strip()

        if self.class_to_cot_map:
            logger.info(f"Detection class map: {self.class_to_cot_map}")

    async def process_detection(
        self, object_name: str, fields: dict[bytes, bytes]
    ) -> None:
        """Process detection data and generate CoT event.

        Args:
            object_name: Name of the detected object
        """
        try:
            lat = fields.get(b"latitude")
            lon = fields.get(b"longitude")
            if not lat or not lon:
                logger.warning(f"Missing location data for detection {object_name}")
                return

            vehicle_id = fields.get(b"id", b"").decode("utf-8")
            cls = fields.get(b"cls", b"unknown").decode("utf-8")
            cot_type = self.class_to_cot_map.get(cls, "a-u-G-I")

            cot_xml = pytak.gen_cot_xml(
                lat=float(lat),
                lon=float(lon),
                uid=f"steeleagle-{object_name}",
                callsign=object_name,
                cot_type=cot_type,
                stale=self.detection_ttl,
            )

            if cot_xml is None:
                logger.error(f"Failed to generate CoT XML for {object_name}")
                return

            cot_xml.set("how", "m-i")  # mensurated (from imagery) location
            cot_xml.set("qos", "5-r-d")  # occasional "push" priority update

            detail = cot_xml.find("detail")
            if detail is None:
                detail = ET.SubElement(cot_xml, "detail")

            link = fields.get(b"link", b"").decode("utf-8")
            if link:
                image_elem = ET.Element("image")
                image_elem.set("url", link)

                try:
                    async with self.http_session.get(link) as response:
                        if response.status == 200:
                            image_data = await response.read()
                            image_elem.set("type", "CP")  # Color Frame Photography
                            image_elem.set("size", str(len(image_data)))
                            image_elem.set(
                                "mime",
                                response.headers.get("Content-Type", "image/jpeg"),
                            )
                            image_elem.text = base64.b64encode(image_data).decode(
                                "utf-8"
                            )
                except Exception as e:
                    logger.debug(f"Failed to fetch image from {link}: {e}")

                detail.append(image_elem)

            remarks_parts = []
            remarks_parts.append(f"vehicle: {vehicle_id}")
            remarks_parts.append(f"class: {cls}")

            confidence = float(fields.get(b"confidence", b"0.0"))
            if confidence:
                remarks_parts.append(f"confidence: {float(confidence)}")

            last_seen = float(fields.get(b"last_seen", b"0.0"))
            if last_seen:
                last_seen_time = datetime.datetime.fromtimestamp(last_seen).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                remarks_parts.append(f"time: {last_seen_time}")

            remarks = ET.Element("remarks")
            remarks.text = " ".join(remarks_parts)
            detail.append(remarks)

            event_xml = ET.tostring(cot_xml, encoding="utf-8")
            await self.handle_data(event_xml)
        except redis.RedisError:
            logger.exception(f"Redis error for detection {object_name}")
        except Exception:
            logger.exception(f"Error processing detection {object_name}")

    async def run_once(self) -> None:
        """Poll Redis for detection updates."""
        try:
            objects = await self.redis_client.zrange("detections", 0, -1)

            for obj_name in objects:
                object_name = obj_name.decode("utf-8")

                # redis type stubs don't properly handle Union[Awaitable[T], T]
                raw = await self.redis_client.hgetall(f"objects:{object_name}")  # type: ignore[return-value]
                fields = cast(dict[bytes, bytes], raw)
                if not fields:
                    continue

                # do not report detections repeatedly
                last_seen = float(fields.get(b"last_seen", b"0.0"))
                last_reported = self._detected.get(object_name)
                if last_reported and (last_seen < last_reported + 60):
                    continue

                await self.process_detection(object_name, fields)
                self._detected[object_name] = last_seen

        except redis.RedisError:
            logger.exception("Redis connection error")


async def async_main(config: SectionProxy) -> None:
    """Main entry point for the daemon.

    Args:
        config: Configuration settings
    """
    # Load config
    redis_host = config.get("REDIS_HOST", fallback="localhost")
    redis_port = int(config.get("REDIS_PORT", fallback=6379))
    redis_username = config.get("REDIS_USERNAME", fallback=None)
    redis_password = config.get("REDIS_PASSWORD", fallback=None)

    # Connect to Redis
    try:
        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            username=redis_username,
            password=redis_password,
            decode_responses=False,  # We need bytes for key parsing
        )
        await redis_client.ping()  # type: ignore[return-value]
        logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
    except redis.ConnectionError:
        logger.exception("Failed to connect to Redis")
        return

    # Create HTTP session for fetching images
    http_session = aiohttp.ClientSession()

    # Initialize PyTAK CLI tool
    pytak_config: SectionProxy | dict = config
    clitool = pytak.CLITool(pytak_config)

    # Instead of calling `await clitool.setup()`
    # avoids 100% CPU usage when we have a write-only connection
    reader, writer = await pytak.protocol_factory(pytak_config)
    if writer:
        write_worker = pytak.TXWorker(clitool.tx_queue, pytak_config, writer)
        clitool.add_task(write_worker)
    if reader:
        read_worker = _RXDrain(clitool.rx_queue, pytak_config, reader)
        clitool.add_task(read_worker)

    # Add our serializer to the task list
    telemetry = TelemetryToCotSerializer(clitool.tx_queue, pytak_config, redis_client)
    clitool.add_tasks({telemetry})

    # Add our serializer to the task list
    if config.getboolean("steeleagle_tak", "detection_poll_enabled"):
        detections = DetectionToCotSerializer(
            clitool.tx_queue, pytak_config, redis_client, http_session
        )
        clitool.add_tasks({detections})

    # Start all tasks
    logger.info("Starting Telemetry-to-CoT daemon...")
    try:
        await clitool.run()
    except asyncio.exceptions.CancelledError:
        pass

    logger.info("Shutting down...")
    await http_session.close()
    await redis_client.aclose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c", "--config", type=Path, default="config.ini", help="configuration file"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="enable verbose logging"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="enable debug logging"
    )
    args = parser.parse_args()

    logger.setLevel(
        logging.DEBUG
        if args.debug
        else logging.INFO
        if args.verbose
        else logging.WARNING
    )

    envvars = {k: v for k, v in os.environ.items() if "%" not in v}
    # envvars.setdefault("REDIS_HOST", "localhost")
    # envvars.setdefault("REDIS_PORT", "6379")
    # envvars.setdefault("REDIS_USERNAME", None)
    # envvars.setdefault("REDIS_PASSWORD", None)
    envvars.setdefault("COT_URL", "tcp://localhost:8087")
    envvars.setdefault("COT_STALE", "120")
    envvars.setdefault("POLL_INTERVAL", "1")
    envvars.setdefault("DETECTION_POLL_ENABLED", "0")
    envvars.setdefault("DETECTION_POLL_INTERVAL", "5")
    envvars.setdefault("DETECTION_TTL", "1200")
    envvars.setdefault("DETECTION_CLASS_MAP", "")
    envvars.setdefault("DEBUG", "1" if args.debug else "0")
    config = ConfigParser(envvars)

    if args.config is not None and args.config.exists():
        config.read(args.config)
    else:
        config.add_section("steeleagle_tak")

    asyncio.run(async_main(config["steeleagle_tak"]), debug=args.debug)


if __name__ == "__main__":
    main()
