from enum import Enum
import subprocess
import sys
import time
from zipfile import ZipFile
import cv2
import numpy as np
import requests
import validators
import zmq
import zmq.asyncio
import json
import os
import asyncio
import logging
from cnc_protocol import cnc_pb2
from gabriel_protocol import gabriel_pb2
from gabriel_client.websocket_client import ProducerWrapper, WebsocketClient
import nest_asyncio

# Apply nest_asyncio to avoid conflicts in asyncio
nest_asyncio.apply()

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Constants and Environment Variables
user_path = './user/project/implementation'
context = zmq.asyncio.Context()
commander_socket = context.socket(zmq.REQ)
user_mission_socket= context.socket(zmq.REQ)
user_cmd_socket = context.socket(zmq.ROUTER)
driver_user_cmd_socket = context.socket(zmq.DEALER)
driver_man_cmd_socket = context.socket(zmq.DEALER)
driver_telemetry_socket = context.socket(zmq.SUB)
driver_camera_socket = context.socket(zmq.SUB)


# Connect Sockets to Addresses from Environment Variables
def setup_socket(socket, socket_type, env_var, logger_message):
    addr = 'tcp://' + os.environ.get(env_var)
    if addr:
        if socket_type == 'connect':
            socket.connect(addr)
        elif socket_type == 'bind':
            socket.bind(addr)
        logger.info(logger_message)
    else:
        logger.error(f'Cannot get {env_var} from system')
        quit()

# Setting up sockets
driver_telemetry_socket.setsockopt(zmq.SUBSCRIBE, b'') # Subscribe to all topics
driver_telemetry_socket.setsockopt(zmq.CONFLATE, 1)
driver_camera_socket.setsockopt(zmq.SUBSCRIBE, b'')  # Subscribe to all topics
driver_camera_socket.setsockopt(zmq.CONFLATE, 1)
setup_socket(commander_socket, 'connect', 'STEELEAGLE_COMMANDER_CMD_REQ_ADDR', 'Created commander_socket endpoint')
setup_socket(user_mission_socket, 'bind', 'STEELEAGLE_USER_MISSION_REQ_ADDR', 'Created user_mission_socket endpoint')
setup_socket(user_cmd_socket, 'bind', 'STEELEAGLE_USER_CMD_ROUTER_ADDR', 'Created user_cmd_socket endpoint')

setup_socket(driver_user_cmd_socket, 'connect', 'STEELEAGLE_DRIVER_CMD_DEALER_ADDR', 'Created driver_man_cmd_socket endpoint')
setup_socket(driver_man_cmd_socket, 'connect', 'STEELEAGLE_DRIVER_CMD_DEALER_ADDR', 'Created driver_man_cmd_socket endpoint')
setup_socket(driver_telemetry_socket, 'bind', 'STEELEAGLE_DRIVER_TEL_SUB_ADDR', 'Connected to telemetry publish endpoint')
setup_socket(driver_camera_socket, 'bind', 'STEELEAGLE_DRIVER_CAM_SUB_ADDR', 'Connected to camera publish endpoint')

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

class Kernel:
        
    def __init__(self, gabriel_server, gabriel_port, type):
        
        # sockect endpoints
        self.command_socket = commander_socket
        self.user_mission_socket = user_mission_socket
        self.user_cmd_socket = user_cmd_socket
        self.driver_user_cmd_socket = driver_user_cmd_socket
        self.driver_man_cmd_socket = driver_man_cmd_socket
        self.driver_telemetry_socket = driver_telemetry_socket
        self.driver_camera_socket = driver_camera_socket
        
            
        # drone info
        self.drone_type = type
        self.drone_id = "ant"
        self.manual = True
        self.telemetry_cache = {
            "location": {
                "latitude": None,
                "longitude": None,
                "altitude": None
            },
            "battery": None,
            "magnetometer": None,
            "bearing": None
        }
        self.frame_cache = {
            "data": None,
            "height": None,
            "width": None,
            "channels": None,
            "id": None
        }
        
        
        # remote compute
        self.gabriel_server = gabriel_server
        self.gabriel_port = gabriel_port
        self.engine_results = {}
        self.gabriel_client_heartbeats = 0
        
        # user defined parameters
        self.model = 'coco'
        self.hsv_upper = [50,255,255]
        self.hsv_lower = [30,100,100]
        
        self.command_seq = 1
        
        
        
    ######################################################## USER ############################################################
    async def user_driver_cmd_proxy(self):
        logger.info('user_driver_cmd_proxy started')
        poller = zmq.asyncio.Poller()
        poller.register(self.user_cmd_socket, zmq.POLLIN)
        poller.register(self.driver_user_cmd_socket, zmq.POLLIN)
        
        while True:
            try:
                socks = dict(await poller.poll())

                # Check for messages on the ROUTER socket
                if self.user_cmd_socket in socks:
                    message = await self.user_cmd_socket.recv_multipart()
                    print("Received message from ROUTER:", message)

                    # Filter the message
                    # if should_forward_message(message):
                    await self.driver_user_cmd_socket.send_multipart(message)


                # Check for messages on the DEALER socket
                if self.driver_user_cmd_socket in socks:
                    message = await self.driver_user_cmd_socket.recv_multipart()
                    print("Received message from DEALER:", message)
                    await user_cmd_socket.send_multipart(message)
                    
            except Exception as e:
                logger.error(f"user_driver_cmd_proxy: {e}")
                
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
            z.extractall(path = user_path)
            self.install_prereqs()
        except Exception as e:
            print(e)
            
    # Function to send a start mission command
    def send_start_mission(self):
        mission_command = cnc_pb2.Mission()
        mission_command.startMission = True
        message = mission_command.SerializeToString()
        print(f'start_mission message:{message}')
        self.user_mission_socket.send(message)
        reply = self.user_mission_socket.recv_string()
        print(f"Mission reply: {reply}")

    # Function to send a stop mission command
    def send_stop_mission(self):
        mission_command = cnc_pb2.Mission()
        mission_command.stopMission = True
        message = mission_command.SerializeToString()
        self.user_mission_socket.send(message)
        reply = self.user_mission_socket.recv_string()
        print(f"Mission reply: {reply}")
    
        
    ######################################################## DRIVER ############################################################ 
    async def telemetry_handler(self):
        logger.info('Telemetry handler started')
        while True:
            try:
                logger.debug(f"telemetry_handler: started time {time.time()}")
                msg = await self.driver_telemetry_socket.recv()
                telemetry = cnc_pb2.Telemetry()
                telemetry.ParseFromString(msg)
                self.telemetry_cache['location']['latitude'] = telemetry.global_position.latitude
                self.telemetry_cache['location']['longitude'] = telemetry.global_position.longitude
                self.telemetry_cache['location']['altitude'] = telemetry.global_position.altitude
                self.telemetry_cache['battery'] = telemetry.battery
                self.telemetry_cache['magnetometer'] = telemetry.mag
                self.telemetry_cache['bearing'] = telemetry.drone_attitude.yaw
                logger.debug(f'Telemetry Data: {self.telemetry_cache}')
                logger.debug(f"telemetry_handler: finished time {time.time()}")
            except Exception as e:
                logger.error(f"Telemetry Handler: {e}")
    
    async def camera_handler(self):
        logger.info('Camera handler started')
        while True:
            try:
                logger.debug(f"Camera Handler: started time {time.time()}")
                msg = await self.driver_camera_socket.recv()
                frame = cnc_pb2.Frame()
                frame.ParseFromString(msg)
                self.frame_cache['data'] = frame.data
                self.frame_cache['height'] = frame.height
                self.frame_cache['width'] = frame.width
                self.frame_cache['channels'] = frame.channels
                self.frame_cache['id'] = frame.id
                logger.debug(f'Camera Frame ID: {self.frame_cache["id"]}')
                logger.debug(f"Camera Handler: finished time {time.time()}")
            except Exception as e:
                logger.error(f"Camera Handler: {e}")

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
            else:
                driver_command.setVelocity.forward_vel = 2 if params["pitch"] > 0 else -2 if params["pitch"] < 0 else 0
                driver_command.setVelocity.angle_vel = 20 if params["yaw"] > 0 else -20 if params["yaw"] < 0 else 0
                driver_command.setVelocity.right_vel = 2 if params["roll"] > 0 else -2 if params["roll"] < 0 else 0
                driver_command.setVelocity.up_vel = 2 if params["thrust"] > 0 else -2 if params["thrust"] < 0 else 0
                logger.debug(f'Driver Command Velocities: {driver_command.setVelocity}')
        elif command == ManualCommand.CONNECTION:
            driver_command.connectionStatus = cnc_pb2.ConnectionStatus()

        
        message = driver_command.SerializeToString()
        await self.driver_man_cmd_socket.send_multipart([message])
        
        if (command == ManualCommand.CONNECTION):
            result = cnc_pb2.Driver()
            while (result.connectionStatus.isConnected == True):
                response = await self.driver_man_cmd_socket.recv()
                result.ParseFromString(response)
            return result

        return None
        

    ######################################################## REMOTE COMPUTE ############################################################           
    def processResults(self, result_wrapper):
        engine_name = result_wrapper.result_producer_name.value
        if engine_name == 'telemetry':
            logger.debug(f'Telemetry received: {result_wrapper}')
        else:
            if len(result_wrapper.results) != 1:
                return

            for result in result_wrapper.results:
                if result.payload_type == gabriel_pb2.PayloadType.TEXT:
                    payload = result.payload.decode('utf-8')
                    data = ""
                    try:
                        if len(payload) != 0:
                            data = json.loads(payload)
                            self.engine_results[engine_name] = result
                    except json.JSONDecodeError as e:
                        logger.debug(f'Error decoding json: {payload}')
                    except Exception as e:
                        logger.error(e)
                else:
                    logger.debug(f"Got result type {result.payload_type}. Expected TEXT.")

    def get_frame_producer(self):
        async def producer():
            await asyncio.sleep(0)
            
            logger.debug(f"Frame Producer: starting converting {time.time()}")
            input_frame = gabriel_pb2.InputFrame()
            if self.frame_cache['data'] is not None:
                try:
                    frame_bytes = self.frame_cache['data']
                    nparr = np.frombuffer(frame_bytes, dtype = np.uint8)
                    frame = cv2.imencode('.jpg', nparr.reshape(self.frame_cache['height'], self.frame_cache['width'], self.frame_cache['channels']))[1]
                    
                    input_frame.payload_type = gabriel_pb2.PayloadType.IMAGE
                    input_frame.payloads.append(frame.tobytes())
                    
                    # produce extras
                    extras = cnc_pb2.Extras()
                    extras.drone_id = self.drone_id
                    extras.location.latitude = self.telemetry_cache['location']['latitude']
                    extras.location.longitude = self.telemetry_cache['location']['longitude']
                    extras.detection_model = self.model
                    extras.lower_bound.H = self.hsv_lower[0]
                    extras.lower_bound.S = self.hsv_lower[1]
                    extras.lower_bound.V = self.hsv_lower[2]
                    extras.upper_bound.H = self.hsv_upper[0]
                    extras.upper_bound.S = self.hsv_upper[1]
                    extras.upper_bound.V = self.hsv_upper[2]
                    if extras is not None:
                        input_frame.extras.Pack(extras)

                except Exception as e:
                    input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
                    input_frame.payloads.append("Unable to produce a frame!".encode('utf-8'))
                    logger.error(f'frame_producer: Unable to produce a frame: {e}')
            else:
                logger.debug('Frame producer: Frame is None')
                input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
                input_frame.payloads.append("Streaming not started, no frame to show.".encode('utf-8'))
                
            logger.debug(f"Frame Producer: finished time {time.time()}")
            return input_frame

        return ProducerWrapper(producer=producer, source_name='telemetry')
    
    def get_telemetry_producer(self):
        async def producer():
            await asyncio.sleep(0)
            
            logger.debug(f"tel Producer: starting time {time.time()}")
            self.gabriel_client_heartbeats += 1
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
            input_frame.payloads.append('heartbeart'.encode('utf8'))

            extras = cnc_pb2.Extras()
            # test
            extras.drone_id = self.drone_id
            extras.status.rssi = 0
            
            try:
                if all(value is None for value in self.telemetry_cache.values()):
                    logger.debug('All telemetry_cache values are None')
                else:
                    # Proceed with normal assignments
                    extras.location.latitude = self.telemetry_cache['location']['latitude']
                    extras.location.longitude = self.telemetry_cache['location']['longitude']
                    extras.location.altitude = self.telemetry_cache['location']['altitude']

                    extras.status.battery = self.telemetry_cache['battery']    
                    extras.status.mag = self.telemetry_cache['magnetometer']
                    extras.status.bearing = self.telemetry_cache['bearing']
                    
                    logger.debug(f'Gabriel Client Telemetry Producer: {extras}')
                
                # result = await self.send_driver_command(ManualCommand.CONNECTION, None)
                # if self.drone_type == DroneType.VESPER:
                #     extras.status.rssi = result.connectionStatus.radio_rssi
                # elif self.drone_type == DroneType.PARROT:
                #     extras.status.rssi = result.connectionStatus.wifi_rssi
                # elif self.drone_type == DroneType.VXOL:
                #     extras.status.rssi = result.connectionStatus.wifi_rssi
                # else:
                #     extras.status.rssi = result.connectionStatus.cellular_rssi
                
                
            except Exception as e:
                logger.debug(f'Gabriel Client Telemetry Producer: {e}')

            # Register on the first frame
            if self.gabriel_client_heartbeats == 1:
                extras.registering = True

            logger.debug('Gabriel Client Telemetry Producer: sending Gabriel frame!')
            input_frame.extras.Pack(extras)
            
            logger.debug(f"tel Producer: finished time {time.time()}")
            return input_frame

        return ProducerWrapper(producer=producer, source_name='telemetry')
    
    
    ######################################################## COMMANDER ############################################################ 
    async def command_handler(self):
        logger.info('Command handler started')
        req = cnc_pb2.Extras()
        req.drone_id = self.drone_id
        while True:
            try:
                await self.command_socket.send(req.SerializeToString())
                rep = await self.command_socket.recv()
                if rep == b'No commands.':
                    logger.debug('No Command received from commander')
                else:
                    extras = cnc_pb2.Extras()
                    extras.ParseFromString(rep)
                    self.command_seq = self.command_seq + 1
                    self.process_command(extras)
            except Exception as e:
                logger.error(f"Command handler error: {e}")
            await asyncio.sleep(0)

    def process_command(self, extras):
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
        logger.info(f"PCMD signal started at: {time.time()}")
        pitch, yaw, roll, thrust = pcmd.pitch, pcmd.yaw, pcmd.roll, pcmd.gaz
        params = {"pitch": pitch, "yaw": yaw, "roll": roll, "thrust": thrust}
        logger.debug(f'PCMD values: {params}')
        asyncio.create_task(self.send_driver_command(ManualCommand.PCMD, params))
            
        
    ######################################################## MAIN ##############################################################             
    async def run(self):
        logger.info('Main: creating gabriel client')
        gabriel_client = WebsocketClient(
            self.gabriel_server, self.gabriel_port,
            [self.get_telemetry_producer(), self.get_frame_producer()], self.processResults
        )
        logger.info('Main: gabriel client created')
        
        try:
            command_coroutine = asyncio.create_task(self.command_handler())
            telemetry_coroutine = asyncio.create_task(self.telemetry_handler())
            camera_coroutine = asyncio.create_task(self.camera_handler())
            gabriel_client.launch()
        except KeyboardInterrupt:
            await self.shutdown(command_coroutine, telemetry_coroutine, camera_coroutine)
        
    async def shutdown(self, *tasks):
        logger.info("Main: Shutting down Kernel")
        self.command_socket.close()
        self.user_mission_socket.close()
        self.driver_man_cmd_socket.close()
        self.driver_telemetry_socket.close()
        self.driver_camera_socket.close()
        context.term()
        for task in tasks:
            task.cancel()
            await task
        
        logger.info("Main: Kernel shutdown complete")
        sys.exit(0)

# Main Execution Block
if __name__ == "__main__":
    logger.info("Main: starting Kernel")
    gabriel_server = os.environ.get('STEELEAGLE_GABRIEL_SERVER')
    logger.info(f'Main: Gabriel server: {gabriel_server}')
    gabriel_port = os.environ.get('STEELEAGLE_GABRIEL_PORT')
    logger.info(f'Main: Gabriel port: {gabriel_port}')
    k = Kernel(gabriel_server, gabriel_port, DroneType.PARROT)
    asyncio.run(k.run())