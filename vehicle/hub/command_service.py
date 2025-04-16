from enum import Enum
import json
import sys
import time
import validators
import zmq
import zmq.asyncio
import asyncio
import logging
import os
import controlplane_pb2 as control_protocol
from service import Service
from util.utils import query_config, setup_logging, SocketOperation

logger = logging.getLogger(__name__)

class CommandService(Service):
    def __init__(self):
        super().__init__()

        # drone info
        self.drone_id = query_config('driver.id')
        self.drone_type = query_config('driver.type')
        self.manual = True

        # init cmd seq
        self.command_seq = 0

        # Setting up sockets

        # Used to receive commands from the commander
        self.commander_socket = self.context.socket(zmq.DEALER)
        self.commander_socket.setsockopt(zmq.IDENTITY, self.drone_id.encode('utf-8'))
        # Used to receive commands from the mission service to be forwarded
        # to the driver
        self.mission_cmd_socket = self.context.socket(zmq.DEALER)
        # Used to communicate with the driver
        self.driver_socket = self.context.socket(zmq.DEALER)
        # Used to request the mission service to perform actions such
        # as downloading, starting, and stopping missions
        self.mission_ctrl_socket = self.context.socket(zmq.REQ)

        self.setup_and_register_socket(
            self.commander_socket, SocketOperation.CONNECT, 'hub.network.controlplane.commander_to_hub')
        self.setup_and_register_socket(
            self.mission_cmd_socket, SocketOperation.BIND, 'hub.network.controlplane.mission_to_hub')
        self.setup_and_register_socket(
            self.driver_socket, SocketOperation.BIND, 'hub.network.controlplane.hub_to_driver')
        self.setup_and_register_socket(
            self.mission_ctrl_socket, SocketOperation.BIND, 'hub.network.controlplane.hub_to_mission')

        self.create_task(self.cmd_proxy())

    def manual_mode_enabled(self):
        self.manual = True

    def manual_mode_disabled(self):
        self.manual = False

    async def send_download_mission(self, req):
        if validators.url(req.auto.url):
            logger.info(f'Downloading flight script sent by commander: {req.auto.url}')
        else:
            logger.info(f'Invalid script URL sent by commander: {req.auto.url}')
            return

        # send the start mission command
        logger.info(f'download_mission message: {req}')
        self.mission_ctrl_socket.send(req.SerializeToString())
        reply = await self.mission_ctrl_socket.recv_string()
        logger.info(f"Mission reply: {reply}")

    # Function to send a start mission command
    async def send_start_mission(self, req):
        # send the start mission command
        logger.info(f'start_mission message: {req}')
        self.mission_ctrl_socket.send(req.SerializeToString())
        reply = await self.mission_ctrl_socket.recv_string()
        logger.info(f"Mission reply: {reply}")

    # Function to send a stop mission command
    async def send_stop_mission(self, req):
        logger.info(f'stop_mission message: {req}')
        self.mission_ctrl_socket.send(req.SerializeToString())
        reply = await self.mission_ctrl_socket.recv_string()
        logger.info(f"Mission reply: {reply}")

    async def send_driver_command(self, req):
        identity = b'cmdr'
        await self.driver_socket.send_multipart([identity, req.SerializeToString()])
        logger.info(f"Command send to driver: {req}")
        
    async def process_command(self, cmd):
        req = control_protocol.Request()
        req.ParseFromString(cmd)

        self.command_seq = self.command_seq + 1

        match req.WhichOneof("type"):
            case "msn":
                # Mission command
                match req.msn.action:
                    case control_protocol.MissionAction.DOWNLOAD:
                        await self.send_download_mission(req)
                    case control_protocol.MissionAction.START:
                        await self.send_start_mission(req)
                        self.manual_mode_disabled()
                    case control_protocol.MissionAction.STOP:
                        await self.send_stop_mission(req)
                        asyncio.create_task(self.send_driver_command(req))
                        self.manual_mode_enabled()
                    case _:
                        raise NotImplemented()
            case "veh":
                # Vehicle command
                if req.veh.HasField("action") and req.veh.action == control_protocol.VehicleAction.RTH:
                    await self.send_stop_mission()
                    asyncio.create_task(self.send_driver_command(req))
                    self.manual_mode_disabled()
                else:
                    task = asyncio.create_task(await self.send_driver_command(req))
                    self.manual_mode_enabled()
            case "cpt":
                # Configure compute command
                raise NotImplemented()
            case None:
                raise Exception("Expected a request type to be specified")

    async def cmd_proxy(self):
        logger.info('cmd_proxy started')
        poller = zmq.asyncio.Poller()
        poller.register(self.commander_socket, zmq.POLLIN)
        poller.register(self.driver_socket, zmq.POLLIN)
        poller.register(self.mission_cmd_socket, zmq.POLLIN)

        while True:
            try:
                logger.debug('proxy loop')
                socks = dict(await poller.poll())

                # Check for messages from CMDR
                if self.commander_socket in socks:
                    msg = await self.commander_socket.recv_multipart()
                    cmd  = msg[0]
                    # Filter the message
                    logger.debug(f"proxy : commander_socket Received message from FRONTEND: cmd: {cmd}")
                    await self.process_command(cmd)

                # Check for messages from MSN
                if self.mission_cmd_socket in socks:
                    msg = await self.mission_cmd_socket.recv_multipart()
                    cmd = msg[0]
                    logger.debug(f"proxy : mission_cmd_socket Received message from FRONTEND: {cmd}")
                    identity = b'usr'
                    await self.driver_socket.send_multipart([identity, cmd])


                # Check for messages from DRIVER
                if self.driver_socket in socks:
                    message = await self.driver_socket.recv_multipart()
                    logger.debug(f"proxy : driver_socket Received message from BACKEND: {message}")

                    # Filter the message
                    identity = message[0]
                    cmd = message[1]
                    logger.debug(f"proxy : driver_socket Received message from BACKEND: identity: {identity} cmd: {cmd}")

                    if identity == b'cmdr':
                        logger.debug(f"proxy : driver_socket Received message from BACKEND: discard bc of cmdr")
                        pass
                    elif identity == b'usr':
                        logger.debug(f"proxy : driver_socket Received message from BACKEND: sent back bc of user")
                        await self.mission_cmd_socket.send_multipart([cmd])
                    else:
                        logger.error(f"proxy: invalid identity")

            except Exception as e:
                logger.error(f"proxy: {e}")

async def main():
    setup_logging(logger, 'hub.logging')
    await CommandService().start()

if __name__ == "__main__":
    logger.info("Main: starting CommandService")

    asyncio.run(main())
