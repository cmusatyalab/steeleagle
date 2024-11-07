#!/usr/bin/env python3

# Copyright (C) 2024 Carnegie Mellon University
# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import asyncio
from datetime import datetime
import sys
import time
import logging
from google.protobuf.message import DecodeError
from google.protobuf import text_format
from cnc_protocol import cnc_pb2
import argparse
import zmq
import zmq.asyncio
import redis

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

async def listen_cmdrs(args, redis):
    ctx = zmq.Context()
    async_ctx = zmq.asyncio.Context()

    cmd_sock = ctx.socket(zmq.REP)
    cmd_sock.bind(f'tcp://*:{args.cmdrport}')

    kernel_sock = async_ctx.socket(zmq.DEALER)
    kernel_sock_identity = b'cmdr'
    kernel_sock.setsockopt(zmq.IDENTITY, kernel_sock_identity)
    kernel_sock.bind(f'tcp://*:{args.droneport}')

    try:
        while True:
            msg = cmd_sock.recv()
            try:
                extras = cnc_pb2.Extras()
                extras.ParseFromString(msg)
                logger.info(f'Request received:\n{text_format.MessageToString(extras)}')
                logger.info(f"request received at: {time.time()}")

                await kernel_sock.send_multipart([msg])
                cmd_sock.send(b'ACK')
                key = redis.xadd(
                        f"commands",
                        {"commander": extras.commander_id, "drone": extras.cmd.for_drone_id, "value": text_format.MessageToString(extras),}
                    )
                logger.debug(f"Updated redis under stream commands at key {key}")
            except Exception as e:
                logger.error(f"error: {e}")

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, shutting down...")

    finally:
        kernel_sock.close()
        cmd_sock.close()
        ctx.term()

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--droneport', type=int, default=5003, help='Specify port to listen for drone requests [default: 5003]')
    parser.add_argument('-s', '--droneip', type=str, default="128.2.213.139", help='ip for kernel')
    parser.add_argument('-c', '--cmdrport', type=int, default=6001, help='Specify port to listen for commander requests [default: 6001]')
    parser.add_argument(
        "-r", "--redis", type=int, default=6379, help="Set port number for redis connection [default: 6379]"
    )
    parser.add_argument(
        "-a", "--auth", default="", help="Share key for redis user."
    )
    args = parser.parse_args()

    r = redis.Redis(host='redis', port=args.redis, username='steeleagle', password=f'{args.auth}',decode_responses=True)
    logger.info(f"Connected to redis on port {args.redis}...")

    logger.info(f'Listening on tcp://{args.droneip}:{args.droneport} for drone requests...')
    logger.info(f'Listening on tcp://*:{args.cmdrport} for commander requests...')

    await listen_cmdrs(args, r)

if __name__ == '__main__':
    asyncio.run(main())
