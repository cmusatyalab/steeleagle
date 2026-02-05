# SPDX-FileCopyrightText: 2026 Carnegie Mellon University
# SPDX-License-Identifier: Apache-2.0

"""Redis Telemetry to Cursor on Target (CoT) Daemon.

This daemon subscribes to Redis telemetry streams from SteelEagle vehicles
and republishes the data as Cursor on Target (CoT) messages using PyTAK.

Usage:
    python -m steeleagle_tak.daemon
"""

from __future__ import annotations

import asyncio
import logging
import os
import xml.etree.ElementTree as ET
from configparser import ConfigParser, SectionProxy

import pytak
import redis


logger = logging.getLogger(__name__)


class TelemetryToCotSerializer(pytak.QueueWorker):
    """Converts Redis telemetry data to Cursor on Target events.

    Subscribes to Redis telemetry streams and generates CoT events
    for each vehicle's location updates.
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

            # logger.debug(f"{telem}")

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

            # Generate CoT event
            cot_xml = pytak.gen_cot_xml(
                lat=float(lat),
                lon=float(lon),
                hae=float(abs_alt),
                uid=f"steeleagle-{vehicle_name}",
                callsign=vehicle_name,
                cot_type="a-f-A-M-H-Q",
                stale=self.stale_time,
            )

            if cot_xml is None:
                logger.error(f"Failed to generate CoT XML for {vehicle_name}")
                return

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


async def async_main() -> None:
    """Main entry point for the daemon."""
    config = ConfigParser()
    config.read_dict(
        {
            "steeleagle_tak": {
                "COT_URL": "tcp://localhost:8087",
                "COT_STALE": "120",
                "POLL_INTERVAL": "1",
                "DEBUG": "0",
            }
        }
    )
    for key, value in os.environ.items():
        if key.startswith(("COT_", "REDIS_", "POLL_", "PYTAK_")):
            config.set("steeleagle_tak", key, value)

    # Load environment variables or config
    redis_host = config.get("steeleagle_tak", "REDIS_HOST", fallback="localhost")
    redis_port = int(config.get("steeleagle_tak", "REDIS_PORT", fallback=6379))
    redis_username = config.get("steeleagle_tak", "REDIS_USERNAME", fallback=None)
    redis_password = config.get("steeleagle_tak", "REDIS_PASSWORD", fallback=None)

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
    clitool = pytak.CLITool(config["steeleagle_tak"])

    # Avoid 100% CPU usage when we have a write-only connection
    # instead of...  await clitool.setup()
    reader, writer = await pytak.protocol_factory(clitool.config)
    if writer:
        write_worker = pytak.TXWorker(clitool.tx_queue, clitool.config, writer)
        clitool.add_task(write_worker)
    if reader:
        read_worker = pytak.RXWorker(clitool.rx_queue, clitool.config, reader)
        clitool.add_task(read_worker)

    # Add our serializer to the task list
    serializer = TelemetryToCotSerializer(
        clitool.tx_queue,
        config["steeleagle_tak"],
        redis_client,
    )
    clitool.add_tasks({serializer})

    # Start all tasks
    logger.info("Starting Telemetry-to-CoT daemon...")
    await clitool.run()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
    )
    # logger.setLevel(logging.DEBUG)
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
