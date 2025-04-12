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
from protocol import controlplane_pb2
from service import Service
from util.utils import import_config, setup_logging, SocketOperation

logger = logging.getLogger(__name__)

class CommandService(Service):
    def __init__(self, config):
        super().__init__()

        driver_config = config.get("driver")
        if driver_config is None:
            logger.fatal("Driver config not available")
        config = config.get('hub')

        # drone info
        self.drone_id = driver_config.get("id")
        self.drone_type = driver_config.get("type")
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
            self.commander_socket, SocketOperation.CONNECT, 'controlplane.commander_to_hub')
        self.setup_and_register_socket(
            self.mission_cmd_socket, SocketOperation.BIND, 'controlplane.mission_to_hub')
        self.setup_and_register_socket(
            self.driver_socket, SocketOperation.BIND, 'controlplane.hub_to_driver')
        self.setup_and_register_socket(
            self.mission_ctrl_socket, SocketOperation.BIND, 'controlplane.hub_to_mission')

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

    async def process_command(self, cmd):
        req = controlplane_pb2.Request()
        req.ParseFromString(cmd)

        self.command_seq = self.command_seq + 1

        match req.WhichOneof("type"):
            case "msn":
                # Mission command
                match req.msn.action:
                    case controlplane_pb2.MissionAction.DOWNLOAD:
                        await self.send_download_mission(req)
                    case controlplane_pb2.MissionAction.START:
                        await self.send_start_mission(req)
                        self.manual_mode_disabled()
                    case controlplane_pb2.MissionAction.STOP:
                        await self.send_stop_mission(req)
                        asyncio.create_task(self.send_driver_command(req))
                        self.manual_mode_enabled()
                    case _:
                        raise NotImplemented()
            case "veh":
                # Vehicle command
                if req.veh.HasField("action") and req.veh.action == controlplane_pb2.VehicleAction.RTH:
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

async def main():
    config_path = os.getenv("CONFIG_PATH")
    if config_path is None:
        raise Exception("Expected CONFIG_PATH env variable to be specified")

    config = import_config(config_path)
    hub_config = config.get("hub")
    if hub_config is None:
        raise Exception("Hub config not available")

    logging_config = hub_config.get('logging')
    setup_logging(logger, logging_config)

    # init CommandService
    cmd_service = CommandService(config)

    # run CommandService
    await cmd_service.start()

if __name__ == "__main__":
    logger.info("Main: starting CommandService")

    asyncio.run(main())
