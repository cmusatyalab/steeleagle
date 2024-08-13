import subprocess
import sys
from zipfile import ZipFile
import requests
import zmq
import json
import os
import asyncio
import logging
from cnc_protocol import cnc_pb2

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Write log messages to stdout so they are readable in Docker logs
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

context = zmq.Context()

# Create socket endpoints for driver
command_server = context.socket(zmq.REQ)
addr = 'tcp://' + os.environ.get('STEELEAGLE_KERNEL_COMMAND_ADDR')
if addr:
    command_server.bind(addr)
    logger.info('Created command server endpoint')
else:
    logger.error('Cannot get command endpoint from system')
    quit()

# # Create a pub/sub socket that telemetry can be read from
# telemetry_socket = context.socket(zmq.PUB)
# tel_pub_addr = 'udp://' + os.environ.get('STEELEAGLE_DRIVER_TEL_PUB_ADDR')
# if tel_pub_addr:
#     telemetry_socket.connect(tel_pub_addr)
#     logger.info('Connected to telemetry publish endpoint')
# else:
#     logger.error('Cannot get telemetry publish endpoint from system')
#     quit()

# # Create a pub/sub socket that the camera stream can be read from
# camera_socket = context.socket(zmq.PUB)
# cam_pub_addr = 'udp://' + os.environ.get('STEELEAGLE_DRIVER_CAM_PUB_ADDR')
# if cam_pub_addr:
#     camera_socket.connect(cam_pub_addr)
#     logger.info('Connected to camera publish endpoint')
# else:
#     logger.error('Cannot get camera publish endpoint from system')
#     quit()


# shared volume for user and kernel space
user_path = './user/project/implementation'

class Kernel:
    def __init__(self):
        self.socket = command_server
    ######################################################## MISSION ############################################################ 
    ######################################################## DRIVER ############################################################ 
    
    ######################################################## COMMAND ############################################################ 
    def install_prereqs(self) -> bool:
        ret = False
        # Pip install prerequsites for flight script
        requirements_path = os.path.join(user_path, 'requirements.txt')
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
                subprocess.check_call(['rm', '-rf', user_path])
            except subprocess.CalledProcessError as e:
                logger.debug(f"Error removing old task/transition defs: {e}")
            z.extractall()
            self.install_prereqs()
        except Exception as e:
            print(e)
        
    # Function to send a start mission command
    def send_start_mission(self):
        mission_command = cnc_pb2.Mission()
        mission_command.startMission = True
        message = mission_command.SerializeToString()
        print(f'start_mission message:{message}')
        self.socket.send(message)
        reply = self.socket.recv_string()
        print(f"Mission reply: {reply}")

    # Function to send a stop mission command
    def send_stop_mission(self):
        mission_command = cnc_pb2.Mission()
        mission_command.stopMission = True
        message = mission_command.SerializeToString()
        self.socket.send(message)
        reply = self.socket.recv_string()
        print(f"Mission reply: {reply}")

    def command_handler(self):
        while True:
            try:
                req = self.socket.recv(flags=zmq.NOBLOCK)
                commander_req = cnc_pb2.Command()
                commander_req.parseFromString(req)
                if commander_req.script_url:
                    self.download_script(commander_req.script_url)
                    self.send_start_mission()
                elif commander_req.manual:
                    self.send_stop_mission()
            
            except zmq.Again:
                pass
            
            except Exception as e:
                logger.debug(e)
                
    def run(self):
        asyncio.create_task(self.command_handler())
        while True:
            asyncio.sleep(1)
    

if __name__ == "__main__":
    print("Starting client")
    k = Kernel()
    
    asyncio.run(k.run())