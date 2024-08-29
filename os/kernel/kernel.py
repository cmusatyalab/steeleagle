from enum import Enum
import subprocess
import sys
from zipfile import ZipFile
import cv2
import numpy as np
import requests
import validators
import zmq
import json
import os
import asyncio
import logging
from cnc_protocol import cnc_pb2
from gabriel_protocol import gabriel_pb2
from gabriel_client.websocket_client import ProducerWrapper, WebsocketClient
import nest_asyncio
import datetime

nest_asyncio.apply()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Write log messages to stdout so they are readable in Docker logs
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

context = zmq.Context()

# Create socket endpoints for commander
commander_socket = context.socket(zmq.REQ)
addr = 'tcp://' + os.environ.get('STEELEAGLE_COMMANDER_CMD_REQ_ADDR')
if addr:
    commander_socket.connect(addr)
    logger.info('Created commander_socket endpoint')
else:
    logger.error('Cannot get commander_socket from system')
    quit()

# Create socket endpoints for userspace
user_socket = context.socket(zmq.REQ)
addr = 'tcp://' + os.environ.get('STEELEAGLE_USER_CMD_REQ_ADDR')
if addr:
    user_socket.bind(addr)
    logger.info('Created user_socket endpoint')
else:
    logger.error('Cannot get user_socket from system')
    quit()

# Create socket endpoints for driver
driver_socket = context.socket(zmq.DEALER)
addr = 'tcp://' + os.environ.get('STEELEAGLE_DRIVER_CMD_DEALER_ADDR')
if addr:
    driver_socket.connect(addr)
    logger.info('Created driver_socket endpoint')
else:
    logger.error('Cannot get driver_socket from system')
    quit()


# Create a pub/sub socket that telemetry can be read from
telemetry_socket = context.socket(zmq.SUB)
telemetry_socket.setsockopt(zmq.SUBSCRIBE, b'') # Subscribe to all topics
telemetry_socket.setsockopt(zmq.CONFLATE, 1)
addr = 'tcp://' + os.environ.get('STEELEAGLE_DRIVER_TEL_SUB_ADDR')
logger.info(f'Telemetry address: {addr}')
if addr:
    telemetry_socket.bind(addr)
    logger.info('Connected to telemetry publish endpoint')
else:
    logger.error('Cannot get telemetry publish endpoint from system')
    quit()

# Create a pub/sub socket that the camera stream can be read from
camera_socket = context.socket(zmq.SUB)
camera_socket.setsockopt(zmq.SUBSCRIBE, b'') # Subscribe to all topics
camera_socket.setsockopt(zmq.CONFLATE, 1)
addr = 'tcp://' + os.environ.get('STEELEAGLE_DRIVER_CAM_SUB_ADDR')
if addr:
    camera_socket.connect(addr)
    logger.info('Connected to camera publish endpoint')
else:
    logger.error('Cannot get camera publish endpoint from system')
    quit()


# shared volume for user and kernel space
user_path = './user/project/implementation'

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
        self.user_socket = user_socket
        self.driver_socket = driver_socket
        self.telemetry_socket = telemetry_socket
        self.camera_socket = camera_socket
            
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
        
        
        
    ######################################################## USER ############################################################ 
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
        self.user_socket.send(message)
        reply = self.user_socket.recv_string()
        print(f"Mission reply: {reply}")

    # Function to send a stop mission command
    def send_stop_mission(self):
        mission_command = cnc_pb2.Mission()
        mission_command.stopMission = True
        message = mission_command.SerializeToString()
        self.user_socket.send(message)
        reply = self.user_socket.recv_string()
        print(f"Mission reply: {reply}")
    
        
    ######################################################## DRIVER ############################################################ 
    async def telemetry_handler(self):
        logger.info('Telemetry handler started')
        
        while True:
            try:
                msg = self.telemetry_socket.recv(flags=zmq.NOBLOCK)
                telemetry = cnc_pb2.Telemetry()
                telemetry.ParseFromString(msg)
                self.telemetry_cache['location']['latitude'] = telemetry.global_position.latitude
                self.telemetry_cache['location']['longitude'] = telemetry.global_position.longitude
                self.telemetry_cache['location']['altitude'] = telemetry.global_position.altitude
                self.telemetry_cache['battery'] = telemetry.battery
                self.telemetry_cache['magnetometer'] = telemetry.mag
                self.telemetry_cache['bearing'] = telemetry.drone_attitude.yaw
                
                logger.debug(f'Telemetry Handler: Latitude: {self.telemetry_cache["location"]["latitude"]} Longitude: {self.telemetry_cache["location"]["longitude"]} Altitude: {self.telemetry_cache["location"]["altitude"]}')
                logger.debug(f'Telemetry Handler: Battery: {self.telemetry_cache["battery"]}')
                logger.debug(f'Telemetry Handler: Magnetometer: {self.telemetry_cache["magnetometer"]}')
                logger.debug(f'Telemetry Handler: Bearing: {self.telemetry_cache["bearing"]}')
            except zmq.Again:
                logger.debug('Telemetry handler no received telemetry')
                pass
            
            except Exception as e:
                logger.error(f"Telemetry Handler: {e}")
                
            await asyncio.sleep(0)
    
    async def camera_handler(self):
        logger.info('Camera handler started')
        while True:
            try:
                msg = self.camera_socket.recv(flags=zmq.NOBLOCK)
                frame = cnc_pb2.Frame()
                frame.ParseFromString(msg)
                self.frame_cache['data'] = frame.data
                self.frame_cache['height'] = frame.height
                self.frame_cache['width'] = frame.width
                self.frame_cache['channels'] = frame.channels
                self.frame_cache['id'] = frame.id
                id = self.frame_cache['id']
                logger.debug(f'Camera Handler: Frame received: {frame}')
                logger.debug('Camera Handler: Timestamp: {:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now()))
                logger.debug(f'Camera Handler: ID: frame_id {id}')
                
            except zmq.Again:
                logger.debug('Camera handler no received camera')
                pass
            except Exception as e:
                logger.error(f"Camera Handler: {e}")
            await asyncio.sleep(0)
            
            
    async def send_driver_command(self, command, params):
        driver_command = cnc_pb2.Driver()

        if command == ManualCommand.RTH:
            driver_command.rth = True
        if command == ManualCommand.HALT:
            driver_command.hover = True
        elif command == ManualCommand.TAKEOFF:
            driver_command.takeOff = True
        elif command == ManualCommand.LAND:
            driver_command.land = True
            
        elif command == ManualCommand.PCMD:
            
            # driver_command.setVelocity.forward_vel = 0.0
            # driver_command.setVelocity.right_vel = 0.0
            # driver_command.setVelocity.up_vel = 0.0
            # driver_command.setVelocity.angle_vel = 0.0
            
            
            
            if ( params["pitch"] == 0 and params["yaw"] == 0 and params["roll"] == 0 and params["thrust"] == 0):
                driver_command.hover = True
            else:
                if params["pitch"] > 0:
                    driver_command.setVelocity.forward_vel = 2
                elif params["pitch"] < 0:
                    driver_command.setVelocity.forward_vel = -2
                
                if params["yaw"] > 0:
                    driver_command.setVelocity.angle_vel = 20
                elif params["yaw"] < 0:
                    driver_command.setVelocity.angle_vel = -20
                
                if params["roll"] > 0:
                    driver_command.setVelocity.right_vel = 2
                elif params["roll"] < 0:
                    driver_command.setVelocity.right_vel = -2
                
                if params["thrust"] > 0:
                    driver_command.setVelocity.up_vel = 2
                elif params["thrust"] < 0:
                    driver_command.setVelocity.up_vel = -2
                                
                logger.debug(f'Thrust: {driver_command.setVelocity.up_vel}')
                logger.debug(f'Pitch: {driver_command.setVelocity.forward_vel }')
                logger.debug(f'Yaw: {driver_command.setVelocity.angle_vel}')
                logger.debug(f'Roll: {driver_command.setVelocity.right_vel}')
            
        elif command == ManualCommand.CONNECTION:
            driver_command.connectionStatus = cnc_pb2.ConnectionStatus()

        message = driver_command.SerializeToString()
        self.driver_socket.send_multipart([message])
        
        if (command == ManualCommand.CONNECTION):
            result = cnc_pb2.Driver()
            while (result.connectionStatus.isConnected == True):
                response = self.driver_socket.recv()
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
                        print(e)
                else:
                    logger.debug(f"Got result type {result.payload_type}. Expected TEXT.")

    def get_frame_producer(self):
        async def producer():
            await asyncio.sleep(0)
            input_frame = gabriel_pb2.InputFrame()
            
            if self.frame_cache['data'] is not None:
                #logger.info('Frame producer: Frame is not None')
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
                    # print the input frame
                    # logger.info(f'Frame producer: Frame produced! {input_frame}')
                except Exception as e:
                    input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
                    input_frame.payloads.append("Unable to produce a frame!".encode('utf-8'))
                    logger.info(f'Unable to produce a frame: {e}')
            else:
                logger.info('Frame producer: Frame is None')
                input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
                input_frame.payloads.append("Streaming not started, no frame to show.".encode('utf-8'))
            return input_frame

        return ProducerWrapper(producer=producer, source_name='telemetry')
    
    def get_telemetry_producer(self):
        async def producer():
            await asyncio.sleep(0)
            self.gabriel_client_heartbeats += 1
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
            input_frame.payloads.append('heartbeart'.encode('utf8'))

            extras = cnc_pb2.Extras()
            # test
            extras.drone_id = self.drone_id
            extras.status.rssi = 0
            
            try:
                extras.location.latitude = self.telemetry_cache['location']['latitude']
                extras.location.longitude = self.telemetry_cache['location']['longitude']
                extras.location.altitude = self.telemetry_cache['location']['altitude']
                logger.debug(f'Gabriel Client Telemetry Producer: Latitude: {extras.location.latitude} Longitude: {extras.location.longitude} Altitude: {extras.location.altitude}')
                    
                extras.status.battery = self.telemetry_cache['battery']    
                extras.status.mag = self.telemetry_cache['magnetometer']
                extras.status.bearing = self.telemetry_cache['bearing']
                logger.debug(f'Gabriel Client Telemetry Producer:: Battery: {extras.status.battery} RSSI: {extras.status.rssi}  Magnetometer: {extras.status.mag} Heading: {extras.status.bearing}')
                
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
            return input_frame

        return ProducerWrapper(producer=producer, source_name='telemetry')
    
    
    ######################################################## COMMANDER ############################################################ 
    async def command_handler(self):
        logger.info('Command handler started')
        req = cnc_pb2.Extras()
        req.drone_id  = self.drone_id
        while True:
            try:
                self.command_socket.send(req.SerializeToString())
                rep = self.command_socket.recv()
                if b'No commands.' == rep:
                    logger.debug(f'No Command received from commander: {rep}')
                else:
                    extras  = cnc_pb2.Extras()
                    extras.ParseFromString(rep)
                    logger.debug(f'Command received from commander: {extras}')
                    if extras.cmd.rth:
                        logger.info('RTH signaled from commander')
                        self.send_stop_mission()
                        asyncio.create_task(self.send_driver_command(ManualCommand.RTH, None))
                        self.manual = False
                    elif extras.cmd.halt:
                        logger.info('Killswitch signaled from commander')
                        self.send_stop_mission()
                        asyncio.create_task(self.send_driver_command(ManualCommand.HALT, None))
                        self.manual = True
                        logger.info('Manual control is now active!')
                    elif extras.cmd.script_url:
                        # Validate url
                        if validators.url(extras.cmd.script_url):
                            logger.info(f'Flight script sent by commander: {extras.cmd.script_url}')
                            self.manual = False
                            # self.download_script(extras.cmd.script_url)
                            self.send_start_mission()
                        else:
                            logger.info(f'Invalid script URL sent by commander: {extras.cmd.script_url}')
                    elif self.manual:
                        if extras.cmd.takeoff:
                            logger.info(f'Received manual takeoff')
                            asyncio.create_task(self.send_driver_command(ManualCommand.TAKEOFF, None))
                        elif extras.cmd.land:
                            logger.info(f'Received manual land')
                            asyncio.create_task(self.send_driver_command(ManualCommand.LAND, None))
                        else:
                            logger.debug(f'Received manual PCMD')
                            pitch = extras.cmd.pcmd.pitch
                            yaw = extras.cmd.pcmd.yaw
                            roll = extras.cmd.pcmd.roll
                            thrust = extras.cmd.pcmd.gaz
                            gimbal_pitch = extras.cmd.pcmd.gimbal_pitch
                            logger.debug(f'Got PCMD values: {pitch} {yaw} {roll} {thrust} {gimbal_pitch}')
                            paras = {"pitch": pitch, "yaw": yaw, "roll":roll, "thrust":thrust}
                            asyncio.create_task(self.send_driver_command(ManualCommand.PCMD, paras))
                            # asyncio.create_task(self.send_driver_command(ManualCommand.Gimbal, paras))

            except Exception as e:
                logger.error(f"command handler: {e}")
            
            await asyncio.sleep(0)
            
        
    ######################################################## MAIN ##############################################################             
    async def run(self):
        logger.info('Main: creating gabriel client')
        gabriel_client = WebsocketClient(
            self.gabriel_server, self.gabriel_port,
            [self.get_telemetry_producer(), self.get_frame_producer()],  self.processResults
        )
        logger.info('Main: gabriel client created')
        
        try:
            command_coroutine = asyncio.create_task(self.command_handler())
            telemetry_coroutine = asyncio.create_task(self.telemetry_handler())
            camera_coroutine = None
            camera_coroutine = asyncio.create_task(self.camera_handler())
            gabriel_client.launch()
                
        except KeyboardInterrupt:
            logger.info("Main: Shutting down Kernel")
            self.command_socket.close()
            self.user_socket.close()
            self.driver_socket.close()
            self.telemetry_socket.close()
            self.camera_socket.close()
            
            command_coroutine.cancel()
            telemetry_coroutine.cancel()
            camera_coroutine.cancel()
            
            await command_coroutine
            await telemetry_coroutine
            await camera_coroutine
            
            logger.info("Main: Kernel shutdown complete")
            sys.exit(0)
        
    

if __name__ == "__main__":
    logger.info("Main: starting Kernel")
    gabriel_server = os.environ.get('STEELEAGLE_GABRIEL_SERVER')
    logger.info(f'Main: Gabriel server: {gabriel_server}')
    gabriel_port = os.environ.get('STEELEAGLE_GABRIEL_PORT')
    logger.info(f'Main: Gabriel port: {gabriel_port}')
    k = Kernel(gabriel_server, gabriel_port, DroneType.PARROT)
    asyncio.run(k.run())
