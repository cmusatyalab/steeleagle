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
import datetime
import logging
import math
import os
import time
import xml.etree.ElementTree as ET
from configparser import ConfigParser, SectionProxy
from pathlib import Path
from typing import Any

import pytak
import redis

logging.basicConfig(format="%(asctime)s %(name)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class RXDrain(pytak.RXWorker):
    async def run_once(self) -> None:
        if self.reader:
            data: bytes = await self.readcot()
            if data:
                self._logger.debug("RX data: %s", data)
                # and drop the data on the floor...


def cot_detail_append(cot_xml: ET.Element, elem: ET.Element) -> None:
    detail = cot_xml.find("detail")
    if detail is None:
        detail = ET.SubElement(cot_xml, "detail")
    detail.append(elem)


def estimate_gps_accuracy(satellites: int) -> dict[str, Any]:
    """Estimate GPS accuracy based on satellite count."""
    if satellites < 4:
        return {
            "status": "NO_FIX",
            "horizontal_error": 15.0,  # meters
            "vertical_error": 30.0,  # meters
            "hdop": 5.0,
        }
    elif satellites < 6:
        return {
            "status": "WEAK_SIGNAL",
            "horizontal_error": 6.5,  # meters
            "vertical_error": 13.0,  # meters
            "hdop": 2.5,
        }
    elif satellites < 8:
        return {
            "status": "MODERATE_ACCURACY",
            "horizontal_error": 2.0,  # meters
            "vertical_error": 4.0,  # meters
            "hdop": 1.2,
        }
    else:
        return {
            "status": "HIGH_ACCURACY",
            "horizontal_error": 1.0,  # meters
            "vertical_error": 2.0,  # meters
            "hdop": 0.6,
        }


class TelemetryToCotSerializer(pytak.QueueWorker):
    """Converts Redis telemetry data to Cursor on Target events.

    Subscribes to Redis telemetry streams, generating CoT events for each
    vehicle's location updates.
    """

    def __init__(
        self,
        queue: asyncio.Queue,
        config: SectionProxy | dict,
        redis_client: redis.Redis,
    ) -> None:
        """Initialize the serializer.

        Args:
            queue: PyTAK event queue to send CoT events to
            config: Configuration with Redis and CoT settings
            redis_client: Connected Redis client
        """
        super().__init__(queue, config)
        self.redis_client = redis_client

        self.poll_interval = float(config.get("POLL_INTERVAL", 1.0))
        self.stale_time = int(config.get("COT_STALE", 120))

        logger.info(f"Initialized with poll interval: {self.poll_interval}s")

    async def handle_data(self, data: ET.Element) -> None:
        """Handle pre-CoT data, serialize to CoT Event, then puts on queue.

        Args:
            data: XML bytes of CoT event to queue
        """
        event_xml = ET.tostring(data, encoding="utf-8")
        # logger.debug(event_xml)
        await self.put_queue(event_xml)

    async def process_vehicle_telemetry(self, vehicle_name: str) -> None:
        """Process latest telemetry for a vehicle and generate CoT event.

        Args:
            vehicle_name: Name of the vehicle to query
        """
        try:
            # Get latest telemetry from Redis stream
            latest = self.redis_client.xrevrange(
                f"telemetry:{vehicle_name}", "+", "-", 1
            )

            if not latest:
                logger.debug(f"No telemetry found for vehicle: {vehicle_name}")
                return

            # Extract the most recent telemetry entry
            _, telem = latest[0]

            logger.debug(f"{telem}")

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

            # Our largest drone, the Spirit, is probably about 1 meter tall.
            drone_size = 1.0

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
                cot_detail_append(cot_xml, track)

            battery = telem.get(b"battery")
            if battery is not None:
                status = ET.Element("status")
                status.set("battery", str(int(battery)))
                cot_detail_append(cot_xml, status)

            # Add any other info as remarks
            additional = [
                f"satellites: {satellites}",
            ]
            remarks = ET.Element("remarks")
            remarks.text = " ".join(additional)
            cot_detail_append(cot_xml, remarks)

            # Not sure what these are for, but least taky seems to need it
            takv = ET.Element("takv")
            takv.set("os", "Linux")
            takv.set("device", "Drone")
            takv.set("version", "1.0")
            takv.set("platform", "SteelEagle")
            cot_detail_append(cot_xml, takv)

            # Convert to bytes and queue
            await self.handle_data(cot_xml)

        except redis.RedisError as e:
            logger.error(f"Redis error for {vehicle_name}: {e}")
        except Exception as e:
            logger.error(f"Error processing {vehicle_name}: {e}")

    async def run(self) -> None:
        """Continuously poll Redis for telemetry updates."""
        logger.info("Starting telemetry poller")

        while True:
            try:
                # Find all active vehicle telemetry streams
                telemetry_keys = self.redis_client.keys("telemetry:*")

                for key in telemetry_keys:
                    vehicle_name = key.decode("utf-8").split(":", 1)[1]
                    await self.process_vehicle_telemetry(vehicle_name)

            except redis.RedisError as e:
                logger.error(f"Redis connection error: {e}")
            except Exception as e:
                logger.error(f"Unexpected error: {e}")

            await asyncio.sleep(self.poll_interval)


class DetectionToCotSerializer(pytak.QueueWorker):
    """Converts Redis detection data to Cursor on Target events.

    Subscribes to Redis detection sets, generating CoT events for detected
    objects.
    """

    def __init__(
        self,
        queue: asyncio.Queue,
        config: SectionProxy | dict,
        redis_client: redis.Redis,
    ) -> None:
        """Initialize the serializer.

        Args:
            queue: PyTAK event queue to send CoT events to
            config: Configuration with Redis and CoT settings
            redis_client: Connected Redis client
        """
        super().__init__(queue, config)
        self.redis_client = redis_client

        self.poll_interval = float(config.get("DETECTION_POLL_INTERVAL", 5.0))
        self.detection_ttl = int(config.get("DETECTION_TTL", 1200))

        detection_class_map = config.get("DETECTION_CLASS_MAP", fallback="")
        self.class_to_cot_map: dict[str, str] = {}
        if detection_class_map:
            for mapping in detection_class_map.split(","):
                parts = mapping.strip().split(":")
                if len(parts) == 2:
                    class_name, cot_type = parts
                    self.class_to_cot_map[class_name.strip()] = cot_type.strip()

        logger.info(f"Initialized with poll interval: {self.poll_interval}s")
        if self.class_to_cot_map:
            logger.info(f"Detection class map: {self.class_to_cot_map}")

    async def handle_data(self, data: ET.Element) -> None:
        """Handle pre-CoT data, serialize to CoT Event, then puts on queue.

        Args:
            data: XML bytes of CoT event to queue
        """
        event_xml = ET.tostring(data, encoding="utf-8")
        logger.debug(event_xml)
        await self.put_queue(event_xml)

    async def process_detection(
        self,
        object_name: str,
        fields: dict[str, str],
    ) -> None:
        """Process detection data and generate CoT event.

        Args:
            object_name: Name of the detected object
            fields: Detection details from Redis hash
        """
        logger.debug(f"{fields}")
        try:
            lat = fields.get(b"latitude")
            lon = fields.get(b"longitude")
            cls = fields.get(b"cls", b"unknown").decode("utf-8")
            confidence = fields.get(b"confidence")
            vehicle_id = fields.get(b"id").decode("utf-8")
            link = fields.get(b"link").decode("utf-8")
            last_seen = fields.get(b"last_seen")

            if not lat or not lon:
                logger.warning(f"Missing location data for detection {object_name}")
                return

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

            cot_xml.set("qos", "5-r-d")  # occasional "push" priority update

            if link:
                image_elem = ET.Element("image")
                image_elem.set("url", link)
                # fetch image
                # image_elem.set("type", "CP")  # Color Frame Photography
                # image_elem.set("size", image.bytes)
                # image_elem.set("mime", image.mimetype)
                # image_elem.set("width", image.width)
                # image_elem.set("height", image.height)
                # image_elem.set("quality", image.compression)
                # image_elem.text = base64-encoded image data
                cot_detail_append(cot_xml, image_elem)

            remarks_parts = []
            if cls:
                remarks_parts.append(f"class: {cls}")
            if confidence:
                remarks_parts.append(f"confidence: {float(confidence)}")
            if vehicle_id:
                remarks_parts.append(f"vehicle: {vehicle_id}")
            if last_seen:
                try:
                    ts = float(last_seen)
                    remarks_parts.append(
                        f"time: {datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                except (ValueError, OSError):
                    remarks_parts.append(f"time: {last_seen}")

            if remarks_parts:
                remarks = ET.Element("remarks")
                remarks.text = " ".join(remarks_parts)
                cot_detail_append(cot_xml, remarks)

            await self.handle_data(cot_xml)

        except redis.RedisError as e:
            logger.error(f"Redis error for detection {object_name}: {e}")
        except Exception as e:
            logger.error(f"Error processing detection {object_name}: {e}")

    async def run(self) -> None:
        """Continuously poll Redis for detection updates."""
        logger.info("Starting detection poller")

        while True:
            try:
                now = time.time()

                objects = self.redis_client.zrange("detections", 0, -1)

                for obj_name in objects:
                    obj_name_str = (
                        obj_name.decode("utf-8")
                        if isinstance(obj_name, bytes)
                        else obj_name
                    )

                    last_seen_ts = self.redis_client.hget(
                        f"objects:{obj_name_str}", "last_seen"
                    )
                    logger.debug(f"{obj_name_str}: {last_seen_ts}")

                    if not last_seen_ts:
                        continue

                    try:
                        last_seen = float(last_seen_ts)
                    except (ValueError, OSError):
                        continue

                    if now - last_seen > self.detection_ttl:
                        continue

                    fields = self.redis_client.hgetall(f"objects:{obj_name_str}")
                    if fields:
                        await self.process_detection(obj_name_str, fields)

            except redis.RedisError as e:
                logger.error(f"Redis connection error: {e}")
            except Exception as e:
                logger.error(f"Unexpected error: {e}")

            await asyncio.sleep(self.poll_interval)


async def async_main(config: SectionProxy) -> None:
    """Main entry point for the daemon."""
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
        redis_client.ping()
        logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {e}")
        return

    # Initialize PyTAK CLI tool
    clitool = pytak.CLITool(config)

    # Instead of calling `await clitool.setup()`
    # avoids 100% CPU usage when we have a write-only connection
    reader, writer = await pytak.protocol_factory(clitool.config)
    if writer:
        write_worker = pytak.TXWorker(clitool.tx_queue, clitool.config, writer)
        clitool.add_task(write_worker)
    if reader:
        read_worker = RXDrain(clitool.rx_queue, clitool.config, reader)
        clitool.add_task(read_worker)

    # Add our serializer to the task list
    telemetry = TelemetryToCotSerializer(clitool.tx_queue, config, redis_client)
    clitool.add_tasks({telemetry})

    # Add our serializer to the task list
    if config.getboolean("steeleagle_tak", "detection_poll_enabled"):
        detections = DetectionToCotSerializer(clitool.tx_queue, config, redis_client)
        clitool.add_tasks({detections})

    # Start all tasks
    logger.info("Starting Telemetry-to-CoT daemon...")
    await clitool.run()


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
