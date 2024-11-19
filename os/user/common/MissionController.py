
import importlib
import os
import subprocess
import shutil
import sys
from zipfile import ZipFile
import requests
import zmq
import asyncio
import logging
from system_call_stubs.DroneStub import DroneStub
# from system_call_stubs.ComputeStub import ComputeStub
from cnc_protocol import cnc_pb2
from util.utils import SocketOperation, setup_socket

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

context = zmq.Context()
msn_sock = context.socket(zmq.REP)
setup_socket(msn_sock, SocketOperation.CONNECT, 'MSN_PORT', 'Connected to user space mission control socket endpoint', os.environ.get("CMD_ENDPOINT"))

user_path = 'user/project/implementation'

class MissionController():
    def __init__(self):
        self.isTerminated = False
        self.tm = None
        self.transitMap = {}
        self.task_arg_map = {}
        self.reload = False
        self.user_path = os.environ.get('PYTHONPATH') + user_path
        logger.info(f"User path: {self.user_path}")
        
    ######################################################## MISSION ############################################################
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
    
    
    def clean_user_path(self):
        for filename in os.listdir(self.user_path):
            file_path = os.path.join(self.user_path, filename)
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)  # Remove directories
            else:
                os.remove(file_path)  # Remove files


    def download_script(self, url):
        # Download zipfile and extract reqs/flight script from cloudlet
        try:
            filename = url.rsplit(sep='/')[-1]
            logger.info(f'Writing {filename} to disk...')
            
            # Download the file
            r = requests.get(url, stream=True)
            r.raise_for_status()  # Raise an error for bad responses
            
            with open(filename, mode='wb') as f:
                for chunk in r.iter_content(chunk_size=8192):  # Use a chunk size
                    f.write(chunk)

            # Open the zip file
            with ZipFile(filename) as z:
                # Check if the path exists and remove it
                if os.path.exists(self.user_path):
                    logger.info(f"Removing old implementation at {self.user_path}")
                    self.clean_user_path()
                else:
                    logger.info(f"{self.user_path} does not exist. No need to remove")

                logger.info(f"Extracting {filename} to {self.user_path}")
                z.extractall(path=self.user_path)

            logger.info(f"Downloaded and extracted {filename} to {self.user_path}")
            self.install_prereqs()
        
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            
    def download_mission(self, url):
        self.download_script(url)
             
    def start_mission(self):
        # check if the mission is already running
        if self.tm:
            logger.info(f"mission already running")
            return
        else: # first time mission, create a task manager
            from common.TaskManager import TaskManager
        
        # dynamic import the fsm
        logger.info(f"start the mission")
        from project.implementation.Mission import Mission
        if self.reload :
            logger.info('Reloading...')
            modules = sys.modules.copy()
            for module_name, module in modules.items():
                logger.info(f"Module name: {module_name}")
                if module_name.startswith('project.implementation.task_defs') or module_name.startswith('project.implementation.Mission') or module_name.startswith('project.implementation.transition_defs'):
                    try:
                        # Log and reload the module
                        logger.info(f"Reloading module: {module_name}")
                        importlib.reload(module)
                    except Exception as e:
                        logger.error(f"Failed to reload module {module_name}: {e}")
                    
        Mission.define_mission(self.transitMap, self.task_arg_map)
        
        # start the tm
        logger.info(f"start the task manager")
        self.tm = TaskManager(self.drone, None, self.transitMap, self.task_arg_map)
        self.tm_coroutine = asyncio.create_task(self.tm.run())
        self.reload = True
        
    
    async def end_mission(self):
        if self.tm and not self.tm_coroutine.cancelled():
            self.tm_coroutine.cancel()
            try:
                await self.tm_coroutine 
            except asyncio.CancelledError:
                logger.info("Mission coroutine was cancelled successfully.")
            except Exception as e:
                logger.error(f"An error occurred while ending the mission: {e}")
            finally:
                self.tm = None
                self.tm_coroutine = None
                logger.info("Mission has been ended and cleaned up.")
        else:
            logger.info("Mission not running or already cancelled.")
            
    ######################################################## MAIN LOOP ############################################################             
    async def run(self):
        self.drone = DroneStub()
        asyncio.create_task(self.drone.run())
        
        # self.compute = ComputeStub()
        while True:
            logger.debug("MC")
            try:
                # Receive a message
                message = msn_sock.recv(flags=zmq.NOBLOCK)
                
                # Log the raw received message
                logger.info(f"Received raw message: {message}")
                
                # Parse the message
                mission_command = cnc_pb2.Mission()
                mission_command.ParseFromString(message)
                logger.info(f"Parsed Command: {mission_command}")
                
                if mission_command.downloadMission:
                    self.download_mission(mission_command.downloadMission)
                    response = "Mission downloaded"
                
                elif mission_command.startMission:
                    self.start_mission()
                    response = "Mission started"
                    
                elif mission_command.stopMission:
                    await self.end_mission()
                    response = "Mission stopped"
                    
                else:
                    response = "Unknown command"

                # Send a reply back to the client
                msn_sock.send_string(response)
                
            except zmq.Again:
                pass
                
            except Exception as e:
                logger.info(f"Failed to parse message: {e}")
                msn_sock.send_string("Error processing command")
            
            await asyncio.sleep(0)
            
            
            

if __name__ == "__main__":
    mc = MissionController()
    asyncio.run(mc.run())