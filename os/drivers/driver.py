import time
import zmq
import zmq.asyncio
import json
import os
import asyncio
import logging
import cnc_protocol.cnc_pb2 as cnc_protocol
from util.utils import setup_socket, SocketOperation
from drivers.ModalAI.Seeker.Seeker import ModalAISeekerDrone, ConnectionFailedException
from drivers.SkyRocket.SkyViper2450GPS.SkyViper2450GPS import SkyViper2450GPSDrone, ConnectionFailedException

# Configure logger
logging_format = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
logging.basicConfig(level=os.environ.get('LOG_LEVEL', logging.INFO),
                    format=logging_format)
logger = logging.getLogger(__name__)

if os.environ.get("LOG_TO_FILE") == "true":
    file_handler = logging.FileHandler('driver.log')
    file_handler.setFormatter(logging.Formatter(logging_format))
    logger.addHandler(file_handler)

telemetry_logger = logging.getLogger('telemetry')
telemetry_handler = logging.FileHandler('telemetry.log')
formatter = logging.Formatter(logging_format)
telemetry_handler.setFormatter(formatter)
telemetry_logger.handlers.clear()
telemetry_logger.addHandler(telemetry_handler)
telemetry_logger.propagate = False

driverArgs = json.loads(os.environ.get('DRIVER_ARGS'))
droneArgs = json.loads(os.environ.get('DRONE_ARGS'))

drone_id = droneArgs.get('id')
drone_type = droneArgs.get('type')
connection_string = droneArgs.get('connection_string')

logger.info(f"Drone ID: {drone_id}")
logger.info(f"Drone Type: {drone_type}")
logger.info(f"Connection String: {connection_string}")

if drone_type == 'ModalAISeeker':
    drone = ModalAISeekerDrone(drone_id)
elif drone_type == 'SkyViper2450GPS':
    drone = SkyViper2450GPSDrone(drone_id)

context = zmq.asyncio.Context()
cmd_back_sock = context.socket(zmq.DEALER)
tel_sock = context.socket(zmq.PUB)
cam_sock = context.socket(zmq.PUB)
tel_sock.setsockopt(zmq.CONFLATE, 1)
cam_sock.setsockopt(zmq.CONFLATE, 1)
setup_socket(tel_sock, SocketOperation.CONNECT, 'TEL_PORT', 'Created telemetry socket endpoint', os.environ.get("DATA_ENDPOINT"))
setup_socket(cam_sock, SocketOperation.CONNECT, 'CAM_PORT', 'Created camera socket endpoint', os.environ.get("DATA_ENDPOINT"))
setup_socket(cmd_back_sock, SocketOperation.CONNECT, 'CMD_BACK_PORT', 'Created command backend socket endpoint', os.environ.get("CMD_ENDPOINT"))


async def camera_stream(drone, cam_sock):
    logger.info('Starting camera stream')
    frame_id = 0
    while await drone.isConnected():
        try:
            cam_message = cnc_protocol.Frame()
            frame, frame_shape = await drone.getVideoFrame()
            
            if frame is None:
                logger.error('Failed to get video frame')
                continue
            
            cam_message.data = frame
            cam_message.height = frame_shape[0]
            cam_message.width = frame_shape[1]
            cam_message.channels = frame_shape[2]
            cam_message.id = frame_id
            cam_sock.send(cam_message.SerializeToString())
            logger.debug(f'Camera stream: sent frame {frame_id}, shape: {frame_shape}')
            frame_id = frame_id + 1
        except Exception as e:
            logger.error(f'Failed to get video frame, error: {e}')
        await asyncio.sleep(0.033)
    logger.info("Camera stream ended, disconnected from drone")

async def telemetry_stream(drone, tel_sock):
    logger.debug('Starting telemetry stream')
    
    await asyncio.sleep(1) # solving for some contention issue with connecting to drone
    
    while await drone.isConnected():
        logger.debug('HI from telemetry stream')
        try:
            tel_message = cnc_protocol.Telemetry()
            telDict = await drone.getTelemetry()
            tel_message.drone_name = telDict["name"]
            # tel_message.mag = telDict["magnetometer"] # type incomaptible with dict provided by nrec driver
            tel_message.battery = telDict["battery"]
            tel_message.drone_attitude.yaw = telDict["attitude"]["yaw"]
            tel_message.drone_attitude.pitch = telDict["attitude"]["pitch"]
            tel_message.drone_attitude.roll = telDict["attitude"]["roll"]
            tel_message.satellites = telDict["satellites"]
            
            tel_message.relative_position.up = telDict["relAlt"]
            
            tel_message.global_position.latitude = telDict["gps"]["latitude"]
            tel_message.global_position.longitude = telDict["gps"]["longitude"]
            tel_message.global_position.altitude = telDict["gps"]["altitude"]
            
            tel_message.velocity.forward_vel = telDict["imu"]["forward"]
            tel_message.velocity.right_vel = telDict["imu"]["right"]
            tel_message.velocity.up_vel = telDict["imu"]["up"]
            
            #tel_message.gimbal_attitude.yaw = telDict["gimbalAttitude"]["yaw"]
            #tel_message.gimbal_attitude.pitch = telDict["gimbalAttitude"]["pitch"]
            #tel_message.gimbal_attitude.roll = telDict["gimbalAttitude"]["roll"]
            
            logger.debug(f"Telemetry: {telDict}")
            tel_sock.send(tel_message.SerializeToString())
            logger.debug('Sent telemetry')
        except Exception as e:
            logger.error(f'Failed to get telemetry, error: {e}')
        await asyncio.sleep(0.01)
    logger.debug("Telemetry stream ended, disconnected from drone")

async def handle(identity, message, resp, action, resp_sock):
    try:
        if action == "takeOff":
            logger.info(f"takeoff function call started at: {time.time()}, seq id {message.seqNum}")
            logger.info('####################################Taking OFF################################################################')
            await drone.takeOff(5)
            resp.resp = cnc_protocol.ResponseStatus.COMPLETED
            logger.info(f"tookoff function call finished at: {time.time()}")
        elif action == "setVelocity":
            velocity = message.setVelocity
            logger.info(f"Setting velocity: {velocity} started at {time.time()}, seq id {message.seqNum}")
            logger.info('####################################Setting Velocity#######################################################################')
            await drone.setVelocity(velocity.forward_vel, velocity.right_vel, velocity.up_vel, velocity.angle_vel)
            resp.resp = cnc_protocol.ResponseStatus.COMPLETED
        elif action == "land":
            logger.info(f"land function call started at: {time.time()}")
            await drone.land()
            resp.resp = cnc_protocol.ResponseStatus.COMPLETED
            logger.info('####################################Landing#######################################################################')
            logger.info(f"land function call finished at: {time.time()}")
        elif action == "rth":
            logger.info(f"rth function call started at: {time.time()}")
            logger.info('####################################Returning to Home#######################################################################')
            await drone.rth()
            resp.resp = cnc_protocol.ResponseStatus.COMPLETED
            logger.info(f"rth function call finished at: {time.time()}")
        elif action == "hover":
            logger.info('####################################Hovering#######################################################################')
            logger.info(f"hover function call started at: {time.time()}, seq id {message.seqNum}")
            await drone.hover()
            logger.info("hover !")
            resp.resp = cnc_protocol.ResponseStatus.COMPLETED
            logger.info(f"hover function call finished at: {time.time()}")
        elif action == "setGPSLocation":
            logger.info(f"setGPSLocation function call started at: {time.time()}")
            logger.info('####################################Setting GPS Location#######################################################################')
            location = message.setGPSLocation
            await drone.setGPSLocation(location.latitude, location.longitude, location.altitude, None)
            resp.resp = cnc_protocol.ResponseStatus.COMPLETED
            logger.info(f"setGPSLocation function call finished at: {time.time()}")
    except Exception as e:
        logger.error(f'Failed to handle command, error: {e.message}')
        resp.resp = cnc_protocol.ResponseStatus.FAILED
    resp_sock.send_multipart([identity, resp.SerializeToString()])


async def main(drone, cam_sock, tel_sock, args):
    while True:
        try:
            logger.info('starting connecting...')
            await drone.connect(connection_string)
            logger.info('drone connected')
        except ConnectionFailedException as e:
            logger.error('Failed to connect to drone, retrying...')
            continue
        logger.info(f'Established connection to drone, ready to receive commands!')
        
        await drone.startStreaming()
        logger.info('Started streaming')
        asyncio.create_task(camera_stream(drone, cam_sock))
        asyncio.create_task(telemetry_stream(drone, tel_sock))

        while await drone.isConnected():
            try:
                message_parts = await cmd_back_sock.recv_multipart()
                identity = message_parts[0]
                logger.info(f"Received identity: {identity}")
                data = message_parts[1]
                logger.info(f"Received data: {data}")
                # Decode message via protobuf, then execute it
                message = cnc_protocol.Driver()
                message.ParseFromString(data)
                logger.info(f"Received message: {message}")
                action = message.WhichOneof("method")

                # Create a driver response message
                resp = message
                asyncio.create_task(handle(identity, message, resp, action, cmd_back_sock))
            except Exception as e:
                logger.info(f'cmd received error: {e}')

        logger.info(f"Disconnected from drone")

if __name__ == "__main__":
    asyncio.run(main(drone, cam_sock, tel_sock, driverArgs))
