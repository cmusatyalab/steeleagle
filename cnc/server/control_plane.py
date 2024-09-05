#!/usr/bin/env python3

# Copyright (C) 2024 Carnegie Mellon University
# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

from datetime import datetime
import sys
import threading
import time
import logging
from google.protobuf.message import DecodeError
from google.protobuf import text_format
from cnc_protocol import cnc_pb2
import argparse
import zmq
import redis

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def listen_cmdrs(args, redis, interrupt):
    ctx = zmq.Context()
    
    cmd_sock = ctx.socket(zmq.REP)
    cmd_sock.bind(f'tcp://*:{args.cmdrport}')
    
    kernel_sock = ctx.socket(zmq.DEALER)
    kernel_sock_identity = b'cmdr'
    kernel_sock.setsockopt(zmq.IDENTITY, kernel_sock_identity)
    kernel_sock.connect(f'tcp://*:{args.droneport}')
    
    
    while not interrupt.isSet():
        msg = cmd_sock.recv()
        try:
            extras = cnc_pb2.Extras()
            extras.ParseFromString(msg)
            logger.info(f'Request received:\n{text_format.MessageToString(extras)}')
            logger.info(f"request received at: {time.time()}")
            kernel_sock.send_multipart([msg])
            cmd_sock.send(b'ACK')
            key = redis.xadd(
                    f"commands",
                    {"commander": extras.commander_id, "drone": extras.cmd.for_drone_id, "value": text_format.MessageToString(extras),}
                )
            logger.debug(f"Updated redis under stream commands at key {key}")
        except DecodeError:
            cmd_sock.send(b'Error decoding protobuf. Did you send a cnc_pb2?')
    
    kernel_sock.close()
    cmd_sock.close()
    ctx.term()
    
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--droneport', type=int, default=5003, help='Specify port to listen for drone requests [default: 6000]')
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

    logger.info(f'Listening on tcp://*:{args.droneport} for drone requests...')
    logger.info(f'Listening on tcp://*:{args.cmdrport} for commander requests...')
    

    try:
        interrupt = threading.Event()
        listen_cmdrs(args, r, interrupt)
    except KeyboardInterrupt:
        interrupt.set()
        logging.info("Waiting for threads to join...")

if __name__ == '__main__':
    main()