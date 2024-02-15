#!/usr/bin/env python3

# Copyright (C) 2024 Carnegie Mellon University
# SPDX-FileCopyrightText: 2024 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import time
import threading
import logging
from gabriel_server import cognitive_engine
from gabriel_protocol import gabriel_pb2
from cnc_protocol import cnc_pb2
import argparse
import zmq
import random
import randomname

def drone(args, ctx, name):
    sock = ctx.socket(zmq.REQ)
    sock.connect(f'tcp://{args.server}:{args.port}')
    print(f'Connected to  on tcp://{args.server}:{args.port} for {name} replies...')
    req = cnc_pb2.Extras()
    req.drone_id = name
    while True:
        try:
            sock.send(req.SerializeToString())
            rep = sock.recv()
            if b'No commands.' != rep:
                print(f"{name} received: {rep}")
        except KeyboardInterrupt:
            break


def cmdr(args,ctx,name):
    sock = ctx.socket(zmq.REQ)
    sock.connect(f'tcp://{args.server}:{args.cport}')
    req = cnc_pb2.Extras()
    req = cnc_pb2.Extras()
    req.cmd.land = True
    req.cmd.pcmd.gaz = -10
    req.commander_id = randomname.get_name()
    req.cmd.for_drone_id = name
    
    try:
        sock.send(req.SerializeToString())
        rep = sock.recv()
        print(f"{req.commander_id} received: {rep}")
    except zmq.Again:
        print(f"No message for {name}.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', default='6000', help='Specify port to listen for drone requests [default: 6000]')
    parser.add_argument('-cp', '--cport', default='6001', help='Specify port to listen for commander requests [default: 6001]')
    parser.add_argument(
        "-s", "--server", default="localhost", help="Address of control plane server."
    )
    args = parser.parse_args()


    ctx = zmq.Context()
    drones = []
    for i in range(0,5):
        name = randomname.get_name(noun=('birds'))
        thread = threading.Thread(target=drone, args=(args,ctx,name))
        thread.daemon = True
        thread.start()
        drones.append(name)

    time.sleep(5)

    while True:
        try:
            thread = threading.Thread(target=cmdr, args=(args,ctx,drones[random.randint(0,len(drones)-1)]))
            thread.daemon = True
            thread.start()
            time.sleep(5)
        except KeyboardInterrupt:
            break


if __name__ == '__main__':
    main()
