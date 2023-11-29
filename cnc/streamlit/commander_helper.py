#!/usr/bin/env python3

# Copyright 2023 Carnegie Mellon University
# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import numpy as np
from gabriel_protocol import gabriel_pb2
from gabriel_client.websocket_client import ProducerWrapper, WebsocketClient
import logging
import zmq
from cnc_protocol import cnc_pb2
import argparse
import os
import asyncio

logger = logging.getLogger(__name__)


class CommanderZmqAdapter:
    def __init__(self, preprocess, args):
        """
        preprocess should take one frame parameter
        produce_engine_fields takes no parameters
        consume_frame should take one frame parameter and one engine_fields
        parameter
        """
        self.commander_id = os.uname()[1]
        self._preprocess = preprocess
        self._source_name = args.source
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind(f"tcp://*:{args.zmqport}")
        logger.info(f"CommanderZmqAdapter bound to {args.zmqport} and awaiting requests...")

    def get_producer_wrappers(self):
        async def producer():
            # await asyncio.sleep(0.1)
            try:
                command = self.socket.recv_json(flags=zmq.NOBLOCK)
                self.socket.send_string("ACK")
            except zmq.ZMQError:
                command = None

            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
            input_frame.payloads.append(bytes("Message to CNC", "utf-8"))

            extras = cnc_pb2.Extras()
            extras.commander_id = self.commander_id
            if command != None:
                extras.cmd.for_drone_id = command["drone_id"]
                if "kill" in command:
                    extras.cmd.halt = True
                elif "script" in command is not None:
                    extras.cmd.manual = False
                    extras.cmd.script_url = command["script"]
                    print(f'Flight script sent: {command["script"]}')
                elif "rth" in command:
                    extras.cmd.manual = False
                    extras.cmd.rth = True
                    print("RTH triggered")
                elif "takeoff" in command:
                    print("Takeoff triggered")
                    extras.cmd.takeoff = True
                elif "land" in command:
                    print("Landing triggered")
                    extras.cmd.land = True
                else:
                    extras.cmd.pcmd.yaw = command["yaw"]
                    extras.cmd.pcmd.pitch = command["pitch"]
                    extras.cmd.pcmd.roll = command["roll"]
                    extras.cmd.pcmd.gaz = command["gaz"]
                    print(
                        f"PCMD: {extras.cmd.pcmd.yaw}, {extras.cmd.pcmd.pitch}, {extras.cmd.pcmd.roll}, {extras.cmd.pcmd.gaz}"
                    )

            input_frame.extras.Pack(extras)
            return input_frame

        return [ProducerWrapper(producer=producer, source_name=self._source_name)]

    def consumer(self, result_wrapper):
        result = result_wrapper.results[0]
        if result.payload_type != gabriel_pb2.PayloadType.TEXT:
            type_name = gabriel_pb2.PayloadType.Name(result.payload_type)
            logger.error("Got result of type %s", type_name)
            return


def preprocess(frame):
    return frame


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--server",
        default="cloudlet033.elijah.cs.cmu.edu",
        help="Specify address of Steel Eagle CNC server [default: cloudlet033.elijah.cs.cmu.edu",
    )
    parser.add_argument(
        "-p", "--port", default="9099", help="Specify Gabriel websocket port [default: 9099]"
    )

    parser.add_argument(
        "-zp", "--zmqport", default="5577", help="Specify ZMQ bind port [default: 5577]"
    )
    parser.add_argument("-l", "--loglevel", default="INFO", help="Set the log level")
    parser.add_argument(
        "-ng",
        "--nogui",
        action="store_true",
        help="If specified, use the text prompt commander",
    )
    parser.add_argument(
        "-sn",
        "--source",
        default="command",
        help="Gabriel Engine Source [default: command]",
    )
    args = parser.parse_args()
    logging.basicConfig(format="%(levelname)s: %(message)s", level=args.loglevel)
    adapter = CommanderZmqAdapter(preprocess, args)

    client = WebsocketClient(
        args.server, args.port, adapter.get_producer_wrappers(), adapter.consumer
    )
    client.launch()


if __name__ == "__main__":
    main()
