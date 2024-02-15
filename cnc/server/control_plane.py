#!/usr/bin/env python3

# Copyright (C) 2024 Carnegie Mellon University
# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

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

interrupt = threading.Event()

def listen_drones(args, drones):
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REP)
    sock.bind(f'tcp://*:{args.droneport}')
    while not interrupt.isSet():
        msg = sock.recv()
        try:
            extras = cnc_pb2.Extras()
            extras.ParseFromString(msg)
            d = drones[extras.drone_id]
            sock.send(d.SerializeToString())
            logger.info(f'Delivered request:\n{text_format.MessageToString(d)}')
            del drones[extras.drone_id]
        except KeyError:
            sock.send(b'No commands.')
        except DecodeError:
            sock.send(b'Error decoding protobuf. Did you send a cnc_pb2?')
    sock.close()

def listen_cmdrs(args, drones, redis):
    ctx = zmq.Context()
    sock = ctx.socket(zmq.REP)
    sock.bind(f'tcp://*:{args.cmdrport}')
    while not interrupt.isSet():
        msg = sock.recv()
        try:
            extras = cnc_pb2.Extras()
            extras.ParseFromString(msg)
            logger.info(f'Request received:\n{text_format.MessageToString(extras)}')
            drones[extras.cmd.for_drone_id] = extras
            sock.send(b'ACK')
            key = redis.xadd(
                    f"commands",
                    {"commander": extras.commander_id, "drone": extras.cmd.for_drone_id, "value": text_format.MessageToString(extras),}
                )
            logger.debug(f"Updated redis under stream commands at key {key}")
        except DecodeError:
            sock.send(b'Error decoding protobuf. Did you send a cnc_pb2?')
    sock.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--droneport', type=int, default=6000, help='Specify port to listen for drone requests [default: 6000]')
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
    drones = {}

    logger.info(f'Listening on tcp://*:{args.droneport} for drone requests...')
    logger.info(f'Listening on tcp://*:{args.cmdrport} for commander requests...')
    
    d = threading.Thread(target=listen_drones, args=[args, drones])
    c = threading.Thread(target=listen_cmdrs, args=[args, drones, r])
    d.start()
    c.start()

    try:
        while d.is_alive():
            time.sleep(0.1)
    except KeyboardInterrupt:
        interrupt.set()
        logging.info("Waiting for threads to join...")
        c.join()
        d.join()

if __name__ == '__main__':
    main()