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
from protocol.steeleagle import controlplane_pb2
from Service import Service
from util.utils import SocketOperation

# Configure logger
logging.basicConfig(level=os.environ.get('LOG_LEVEL', logging.INFO),
                    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

class CommandService(Service):
    def __init__(self, drone_id, drone_type):
        super().__init__()
        # drone info
        self.drone_type = drone_type
        self.drone_id = drone_id
        self.manual = True

        # init cmd seq
        self.command_seq = 0

        # Setting up sockets
        self.cmd_front_cmdr_sock = context.socket(zmq.DEALER)
        self.cmd_front_cmdr_sock.setsockopt(zmq.IDENTITY, self.drone_id.encode('utf-8'))
        self.cmd_front_usr_sock = context.socket(zmq.DEALER)
        self.cmd_back_sock = context.socket(zmq.DEALER)
        self.msn_sock = context.socket(zmq.REQ)

        gabriel_server_host = os.environ.get('STEELEAGLE_GABRIEL_SERVER')
        if gabriel_server_host is None:
            raise Exception("Gabriel server host must be specified using STEELEAGLE_GABRIEL_SERVER")

        self.setup_and_register_socket(
            self.cmd_front_cmdr_sock, SocketOperation.CONNECT,
            'CMD_FRONT_CMDR_PORT', 'Connected command frontend cmdr socket endpoint',
            gabriel_server_host)
        self.setup_and_register_socket(
            self.cmd_front_usr_sock, SocketOperation.BIND, 'CMD_FRONT_USR_PORT',
            'Created command frontend user socket endpoint')
        self.setup_and_register_socket(
            self.cmd_back_sock, SocketOperation.BIND, 'CMD_BACK_PORT',
            'Created command backend socket endpoint')
        self.setup_and_register_socket(
            self.msn_sock, SocketOperation.BIND, 'MSN_PORT',
            'Created userspace mission control socket endpoint')

        self.create_task(self.cmd_proxy())

    def manual_mode_enabled():
        self.manual = True

    def manual_mode_disabled():
        self.manual = False

    async def send_download_mission(self, req):
        if validators.url(req.auto.url):
            logger.info(f'Downloading flight script sent by commander: {req.auto.url}')
        else:
            logger.info(f'Invalid script URL sent by commander: {req.auto.url}')
            return

        # send the start mission command
        logger.info(f'download_mission message: {req}')
        self.msn_sock.send(req.SerializeToString())
        reply = await self.msn_sock.recv_string()
        logger.info(f"Mission reply: {reply}")

    # Function to send a start mission command
    async def send_start_mission(self, req):
        # send the start mission command
        logger.info(f'start_mission message: {req}')
        self.msn_sock.send(req.SerializeToString())
        reply = await self.msn_sock.recv_string()
        logger.info(f"Mission reply: {reply}")

    # Function to send a stop mission command
    async def send_stop_mission(self, req):
        logger.info(f'stop_mission message: {req}')
        self.msn_sock.send(req.SerializeToString())
        reply = await self.msn_sock.recv_string()
        logger.info(f"Mission reply: {reply}")


    async def send_driver_command(self, req):
        identity = b'cmdr'
        await self.cmd_back_sock.send_multipart([identity, req.SerializeToString()])
        logger.info(f"Command send to driver: {req}")

    async def cmd_proxy(self):
        logger.info('cmd_proxy started')
        poller = zmq.asyncio.Poller()
        poller.register(self.cmd_front_cmdr_sock, zmq.POLLIN)
        poller.register(self.cmd_back_sock, zmq.POLLIN)
        poller.register(self.cmd_front_usr_sock, zmq.POLLIN)

        while True:
            try:
                logger.debug('proxy loop')
                socks = dict(await poller.poll())

                # Check for messages from CMDR
                if self.cmd_front_cmdr_sock in socks:
                    msg = await self.cmd_front_cmdr_sock.recv_multipart()
                    cmd  = msg[0]
                    # Filter the message
                    logger.debug(f"proxy : cmd_front_cmdr_sock Received message from FRONTEND: cmd: {cmd}")
                    await self.process_command(cmd)

                # Check for messages from MSN
                if self.cmd_front_usr_sock in socks:
                    msg = await self.cmd_front_usr_sock.recv_multipart()
                    cmd = msg[0]
                    logger.debug(f"proxy : cmd_front_usr_sock Received message from FRONTEND: {cmd}")
                    identity = b'usr'
                    await self.cmd_back_sock.send_multipart([identity, cmd])


                # Check for messages from DRIVER
                if self.cmd_back_sock in socks:
                    message = await self.cmd_back_sock.recv_multipart()
                    logger.debug(f"proxy : cmd_back_sock Received message from BACKEND: {message}")

                    # Filter the message
                    identity = message[0]
                    cmd = message[1]
                    logger.debug(f"proxy : cmd_back_sock Received message from BACKEND: identity: {identity} cmd: {cmd}")

                    if identity == b'cmdr':
                        logger.debug(f"proxy : cmd_back_sock Received message from BACKEND: discard bc of cmdr")
                        pass
                    elif identity == b'usr':
                        logger.debug(f"proxy : cmd_back_sock Received message from BACKEND: sent back bc of user")
                        await self.cmd_front_usr_sock.send_multipart([cmd])
                    else:
                        logger.error(f"proxy: invalid identity")

            except Exception as e:
                logger.error(f"proxy: {e}")

    async def process_command(self, cmd):
        req = controlplane_pb2.Request()
        req.ParseFromString(cmd)

        self.command_seq = self.command_seq + 1

        match req.WhichOneof("type"):
            match "msn":
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
            match "veh":
                # Vehicle command
                if req.veh.HasField("action") and req.veh.action == controlplane_pb2.VehicleAction.RTH:
                    await self.send_stop_mission()
                    asyncio.create_task(self.send_driver_command(req))
                    self.manual_mode_disabled()
                else:
                    task = asyncio.create_task(await self.send_driver_command(req))
                    self.manual_mode_enabled()
            match "cpt":
                # Configure compute command
                raise NotImplemented()
            match None:
                raise Exception("Expected a request type to be specified")

async def main():
    drone_args = os.environ.get('DRONE_ARGS')
    if drone_args == None:
        raise Exception("Expected drone args to be specified")
    droneArgs = json.loads(drone_args)
    drone_id = droneArgs.get('id')
    drone_type = droneArgs.get('type')
    # init CommandService
    cmd_service = CommandService(drone_id, drone_type)

    # run CommandService
    await cmd_service.start()

if __name__ == "__main__":
    logger.info("Main: starting CommandService")

    asyncio.run(main())
