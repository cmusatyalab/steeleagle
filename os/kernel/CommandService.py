from enum import Enum
import sys
import time
import validators
import zmq
import zmq.asyncio
import asyncio
import logging
import os
from cnc_protocol import cnc_pb2
from kernel.Service import Service
from util.utils import setup_socket, SocketOperation

# Configure logger
logging.basicConfig(level=os.environ.get('LOG_LEVEL', logging.INFO),
                    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# Enumerations for Commands and Drone Types
class ManualCommand(Enum):
    RTH = 1
    HALT = 2
    TAKEOFF = 4
    LAND = 5
    PCMD = 6
    CONNECTION = 7
    GIMBAL = 8


class CommandService(Service):
    def __init__(self, drone_id, drone_type):
        super().__init__()
        # drone info
        self.drone_type = drone_type
        self.drone_id = drone_id
        self.manual = True
        
        # init cmd seq
        self.command_seq = 0

        # Setting up conetxt
        context = zmq.asyncio.Context()

        # Setting up sockets
        cmd_front_cmdr_sock = context.socket(zmq.DEALER)
        cmd_front_cmdr_sock.setsockopt(zmq.IDENTITY, self.drone_id.encode('utf-8'))
        cmd_front_usr_sock = context.socket(zmq.DEALER)
        cmd_back_sock = context.socket(zmq.DEALER)
        msn_sock = context.socket(zmq.REQ)
        setup_socket(cmd_front_cmdr_sock, SocketOperation.CONNECT, 'CMD_FRONT_CMDR_PORT', 'Connected command frontend cmdr socket endpoint', os.environ.get('STEELEAGLE_GABRIEL_SERVER'))
        setup_socket(cmd_front_usr_sock, SocketOperation.BIND, 'CMD_FRONT_USR_PORT', 'Created command frontend user socket endpoint')
        setup_socket(cmd_back_sock, SocketOperation.BIND, 'CMD_BACK_PORT', 'Created command backend socket endpoint')
        setup_socket(msn_sock, SocketOperation.BIND, 'MSN_PORT', 'Created userspace mission control socket endpoint')
        self.cmd_front_cmdr_sock = cmd_front_cmdr_sock
        self.cmd_front_usr_sock = cmd_front_usr_sock   
        self.cmd_back_sock = cmd_back_sock
        self.msn_sock = msn_sock
        

        # setting up tasks
        cmd_task = asyncio.create_task(self.cmd_proxy())

        # registering context, sockets and tasks to service
        self.register_context(context)
        self.register_socket(cmd_front_cmdr_sock)
        self.register_socket(cmd_back_sock)
        self.register_socket(msn_sock)
        self.register_task(cmd_task)

    ######################################################## USER ############################################################
    async def send_download_mission(self, url):
        # send the start mission command
        mission_command = cnc_pb2.Mission()
        mission_command.downloadMission = url
        message = mission_command.SerializeToString()
        logger.info(f'download_mission message:{message}')
        self.msn_sock.send(message)
        reply = await self.msn_sock.recv_string()
        logger.info(f"Mission reply: {reply}")

    # Function to send a start mission command
    async def send_start_mission(self):
        # send the start mission command
        mission_command = cnc_pb2.Mission()
        mission_command.startMission = True
        message = mission_command.SerializeToString()
        logger.info(f'start_mission message:{message}')
        self.msn_sock.send(message)
        reply = await self.msn_sock.recv_string()
        logger.info(f"Mission reply: {reply}")

    # Function to send a stop mission command
    async def send_stop_mission(self):
        mission_command = cnc_pb2.Mission()
        mission_command.stopMission = True
        message = mission_command.SerializeToString()
        self.msn_sock.send(message)
        reply = await self.msn_sock.recv_string()
        logger.info(f"Mission reply: {reply}")


    ######################################################## DRIVER ############################################################
    async def send_driver_command(self, command, params):
        driver_command = cnc_pb2.Driver()
        driver_command.seqNum = self.command_seq

        if command == ManualCommand.RTH:
            driver_command.rth = True
            logger.info(f"rth signal sent at: {time.time()}, seq id {driver_command.seqNum}")
        if command == ManualCommand.HALT:
            driver_command.hover = True
        elif command == ManualCommand.TAKEOFF:
            driver_command.takeOff = True
            logger.info(f"takeoff signal sent at: {time.time()}, seq id  {driver_command.seqNum}")
        elif command == ManualCommand.LAND:
            driver_command.land = True

        elif command == ManualCommand.PCMD:
            if params and all(value == 0 for value in params.values()):
                driver_command.hover = True
            else:
                driver_command.setVelocity.forward_vel = params["pitch"]
                driver_command.setVelocity.angle_vel = params["yaw"]
                driver_command.setVelocity.right_vel = params["roll"]
                driver_command.setVelocity.up_vel = params["thrust"]
                logger.info(f'Driver Command setVelocities: {driver_command.setVelocity} sent at:{time.time()}, seq id {driver_command.seqNum}')
        elif command == ManualCommand.GIMBAL:
            driver_command.setGimbal.pitch_theta = params["gimbal_pitch"]
            logger.info(f'Driver Command setGimbal: {driver_command.setGimbal} sent at:{time.time()}, seq id {driver_command.seqNum}')
        elif command == ManualCommand.CONNECTION:
            driver_command.connectionStatus = cnc_pb2.ConnectionStatus()

        message = driver_command.SerializeToString()
        identity = b'cmdr'
        await self.cmd_back_sock.send_multipart([identity, message])
        logger.info(f"Driver Command sent: {message}")
        
        return None

    ######################################################## COMMAND ############################################################
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
        extras = cnc_pb2.Extras()
        extras.ParseFromString(cmd)
        self.command_seq = self.command_seq + 1

        if extras.cmd.rth:
            logger.info(f"RTH signal started at: {time.time()}")
            await self.send_stop_mission()
            asyncio.create_task(self.send_driver_command(ManualCommand.RTH, None))
            self.manual = False
        elif extras.cmd.halt:
            logger.info(f"Halt signal started at: {time.time()}")
            await self.send_stop_mission()
            asyncio.create_task(self.send_driver_command(ManualCommand.HALT, None))
            self.manual = True
            logger.info('Manual control is now active!')
        elif extras.cmd.script_url:
            url = extras.cmd.script_url
            if validators.url(url):
                logger.info(f'Flight script sent by commander: {url}')
                self.manual = False
                await self.send_download_mission(url)
                await self.send_start_mission()
            else:
                logger.info(f'Invalid script URL sent by commander: {extras.cmd.script_url}')
        elif self.manual:
            if extras.cmd.takeoff:
                logger.info(f"takeoff signal started at: {time.time()} seq id {self.command_seq}")
                asyncio.create_task(self.send_driver_command(ManualCommand.TAKEOFF, None))
            elif extras.cmd.land:
                logger.info(f"land signal started at: {time.time()}")
                asyncio.create_task(self.send_driver_command(ManualCommand.LAND, None))
            else:
                self.handle_pcmd_command(extras.cmd.pcmd)

    def handle_pcmd_command(self, pcmd):
        pitch, yaw, roll, thrust, gimbal_pitch = pcmd.pitch, pcmd.yaw, pcmd.roll, pcmd.gaz, pcmd.gimbal_pitch
        params = {"pitch": pitch, "yaw": yaw, "roll": roll, "thrust": thrust, "gimbal_pitch": gimbal_pitch}
        logger.info(f"PCMD signal started at: {time.time()} PCMD values: {params} seq id {self.command_seq}")
        asyncio.create_task(self.send_driver_command(ManualCommand.PCMD, params))
        asyncio.create_task(self.send_driver_command(ManualCommand.GIMBAL, params))


######################################################## MAIN ##############################################################
async def async_main():
    drone_type = os.environ.get('DRONE_TYPE')
    drone_id = os.environ.get('DRONE_ID')
    # init CommandService
    cmd_service = CommandService(drone_id, drone_type)

    # run CommandService
    await cmd_service.start()



# Main Execution Block
if __name__ == "__main__":
    logger.info("Main: starting CommandService")

    asyncio.run(async_main())
