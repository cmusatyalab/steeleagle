from enum import Enum
import subprocess
import sys
import time
from zipfile import ZipFile
import requests
import validators
import zmq
import zmq.asyncio
import os
import asyncio
import logging
from cnc_protocol import cnc_pb2
from kernel.Service import Service
from util.utils import setup_socket

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)



# Enumerations for Commands and Drone Types
class ManualCommand(Enum):
    RTH = 1
    HALT = 2
    TAKEOFF = 4
    LAND = 5
    PCMD = 6
    CONNECTION = 7

class DroneType(Enum):
    PARROT = 1
    VXOL = 2
    VESPER = 3

class CommandService(Service):
    def __init__(self, type, user_path):
        super().__init__()
        
        # setting args
        # drone info
        self.drone_type = type
        self.manual = True
        # init cmd seq
        self.command_seq = 0
        # user path
        self.user_path = user_path
        
        # Setting up conetxt
        context = zmq.asyncio.Context()
        
        # Setting up sockets
        cmd_front_sock = context.socket(zmq.ROUTER)
        cmd_back_sock = context.socket(zmq.DEALER)
        msn_sock = context.socket(zmq.REQ)
        self.cmd_front_sock = cmd_front_sock
        self.cmd_back_sock = cmd_back_sock
        self.msn_sock = msn_sock
        setup_socket(cmd_front_sock, 'bind', 'CMD_FRONT_PORT', 'Created command frontend socket endpoint')
        setup_socket(cmd_back_sock, 'bind', 'CMD_BACK_PORT', 'Created command backend socket endpoint')
        setup_socket(msn_sock, 'bind', 'MSN_PORT', 'Created user space mission control socket endpoint')
        
        # setting up tasks
        cmd_task = asyncio.create_task(self.cmd_proxy())
        
        # registering context, sockets and tasks to service
        self.register_context(context)
        self.register_socket(cmd_front_sock)
        self.register_socket(cmd_back_sock)
        self.register_socket(msn_sock)
        self.register_task(cmd_task)
 
    ######################################################## USER ############################################################
    def install_prereqs(self) -> bool:
        ret = False
        # Pip install prerequsites for flight script
        requirements_path = os.path.join(self.user_path, 'requirements.txt')
        try:
            subprocess.check_call(['python3', '-m', 'pip', 'install', '-r', requirements_path])
            ret = True
        except subprocess.CalledProcessError as e:
            logger.debug(f"Error pip installing requirements.txt: {e}")
        return ret

    def download_script(self, url):
        #download zipfile and extract reqs/flight script from cloudlet
        try:
            filename = url.rsplit(sep='/')[-1]
            logger.info(f'Writing {filename} to disk...')
            r = requests.get(url, stream=True)
            with open(filename, mode='wb') as f:
                for chunk in r.iter_content():
                    f.write(chunk)
            z = ZipFile(filename)
            try:
                subprocess.check_call(['rm', '-rf', self.user_path])
            except subprocess.CalledProcessError as e:
                logger.debug(f"Error removing old task/transition defs: {e}")
            z.extractall(path = self.user_path)
            self.install_prereqs()
        except Exception as e:
            print(e)
            
    # Function to send a start mission command
    def send_start_mission(self, url):
        # download the script
        self.download_script(url)
        
        # send the start mission command
        mission_command = cnc_pb2.Mission()
        mission_command.startMission = True
        message = mission_command.SerializeToString()
        print(f'start_mission message:{message}')
        self.msn_sock.send(message)
        reply = self.msn_sock.recv_string()
        print(f"Mission reply: {reply}")

    # Function to send a stop mission command
    def send_stop_mission(self):
        mission_command = cnc_pb2.Mission()
        mission_command.stopMission = True
        message = mission_command.SerializeToString()
        self.msn_sock.send(message)
        reply = self.msn_sock.recv_string()
        print(f"Mission reply: {reply}")
    
        
    ######################################################## DRIVER ############################################################ 
    async def send_driver_command(self, command, params):
        driver_command = cnc_pb2.Driver()
        driver_command.seqNum = self.command_seq
        
        if command == ManualCommand.RTH:
            driver_command.rth = True
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
                # driver_command.setVelocity.forward_vel = 0
                # driver_command.setVelocity.angle_vel = 0
                # driver_command.setVelocity.right_vel = 0
                # driver_command.setVelocity.up_vel = 0
            else:
                driver_command.setVelocity.forward_vel = 2 if params["pitch"] > 0 else -2 if params["pitch"] < 0 else 0
                driver_command.setVelocity.angle_vel = 20 if params["yaw"] > 0 else -20 if params["yaw"] < 0 else 0
                driver_command.setVelocity.right_vel = 2 if params["roll"] > 0 else -2 if params["roll"] < 0 else 0
                driver_command.setVelocity.up_vel = 2 if params["thrust"] > 0 else -2 if params["thrust"] < 0 else 0
                logger.info(f'Driver Command setVelocities: {driver_command.setVelocity} sent at:{time.time()}, seq id {driver_command.seqNum}')
        elif command == ManualCommand.CONNECTION:
            driver_command.connectionStatus = cnc_pb2.ConnectionStatus()

        
        message = driver_command.SerializeToString()
        identity = b'cmdr'
        await self.cmd_back_sock.send_multipart([identity, message])
        
        # if (command == ManualCommand.CONNECTION):
        #     result = cnc_pb2.Driver()
        #     while (result.connectionStatus.isConnected == True):
        #         response = await self.driver_man_cmd_socket.recv()
        #         result.ParseFromString(response)
        #     return result

        return None
    
    ######################################################## COMMAND ############################################################ 
    async def cmd_proxy(self):
        logger.info('cmd_proxy started')
        poller = zmq.asyncio.Poller()
        poller.register(self.cmd_front_sock, zmq.POLLIN)
        poller.register(self.cmd_back_sock, zmq.POLLIN)
        
        while True:
            try:
                logger.debug('proxy loop')
                socks = dict(await poller.poll())

                # Check for messages on the ROUTER socket
                if self.cmd_front_sock in socks:
                    message = await self.cmd_front_sock.recv_multipart()
                    logger.debug(f"proxy : 1 Received message from BACKEND: {message}")

                    # Filter the message
                    identity = message[0]
                    cmd = message[1]
                    logger.debug(f"proxy : 2 Received message from BACKEND: identity: {identity}")
                    
                    if identity == b'cmdr':
                        self.process_command(cmd)
                    elif identity == b'usr':
                        await self.cmd_back_sock.send_multipart(message)
                    else:
                        logger.error(f"cmd_proxy: invalid identity")


                # Check for messages on the DEALER socket
                if self.cmd_back_sock in socks:
                    message = await self.cmd_back_sock.recv_multipart()
                    logger.debug(f"proxy : 3 Received message from FRONTEND: {message}")

                    # Filter the message
                    identity = message[0]
                    cmd = message[1]
                    logger.debug(f"proxy : 4 Received message from FRONTEND: identity: {identity}")
                    
                    if identity == b'cmdr':
                        logger.debug(f"proxy : 5 Received message from FRONTEND: discard bc of cmdr")
                        pass
                    elif identity == b'usr':
                        logger.debug(f"proxy : 5 Received message from FRONTEND: sent back bc of user")
                        await self.cmd_front_sock.send_multipart(message)
                    else:
                        logger.error(f"cmd_proxy: invalid identity")
                    
            except Exception as e:
                logger.error(f"cmd_proxy: {e}")
                
    def process_command(self, cmd):
        extras = cnc_pb2.Extras()
        extras.ParseFromString(cmd)
        self.command_seq = self.command_seq + 1
               
        if extras.cmd.rth:
            logger.info(f"RTH signal started at: {time.time()}")
            self.send_stop_mission()
            asyncio.create_task(self.send_driver_command(ManualCommand.RTH, None))
            self.manual = False
        elif extras.cmd.halt:
            logger.info(f"Halt signal started at: {time.time()}")
            self.send_stop_mission()
            asyncio.create_task(self.send_driver_command(ManualCommand.HALT, None))
            self.manual = True
            logger.info('Manual control is now active!')
        elif extras.cmd.script_url:
            if validators.url(extras.cmd.script_url):
                logger.info(f'Flight script sent by commander: {extras.cmd.script_url}')
                self.manual = False
                self.send_start_mission()
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
        pitch, yaw, roll, thrust = pcmd.pitch, pcmd.yaw, pcmd.roll, pcmd.gaz
        params = {"pitch": pitch, "yaw": yaw, "roll": roll, "thrust": thrust}
        logger.info(f"PCMD signal started at: {time.time()} PCMD values: {params} seq id {self.command_seq}")
        asyncio.create_task(self.send_driver_command(ManualCommand.PCMD, params))
            
        
######################################################## MAIN ##############################################################             
async def async_main():
    type = DroneType.PARROT
    
    # Constants and Environment Variables
    user_path = './user/project/implementation'

    # init CommandService
    cmd_service = CommandService(type, user_path)
    
    # run CommandService
    await cmd_service.start()
    
    

# Main Execution Block
if __name__ == "__main__":
    logger.info("Main: starting CommandService")
    
    asyncio.run(async_main())
