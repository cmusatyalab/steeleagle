import time
import zmq
import json
import os
import sys
import asyncio
import logging
import cnc_protocol.cnc_pb2 as cnc_protocol
from parrotdrone import ParrotDrone, ConnectionFailedException, ArgumentOutOfBoundsException
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

driverArgs = json.loads(os.environ.get('STEELEAGLE_DRIVER_ARGS'))
droneArgs = json.loads(os.environ.get('STEELEAGLE_DRONE_ARGS'))
drone = ParrotDrone(**droneArgs)

context = zmq.Context()
# Create a response socket connected to the kernel
command_socket = context.socket(zmq.ROUTER)
kernel_addr = 'tcp://' + os.environ.get('STEELEAGLE_DRIVER_CMD_ROUTER_ADDR')
if kernel_addr:
    command_socket.bind(kernel_addr)
    logger.info('Connected to kernel endpoint')
else:
    logger.error('Cannot get kernel endpoint from system')
    quit()

# Create a pub/sub socket that telemetry can be read from
telemetry_socket = context.socket(zmq.PUB)
telemetry_socket.setsockopt(zmq.CONFLATE, 1)
tel_pub_addr = 'tcp://' + os.environ.get('STEELEAGLE_DRIVER_TEL_PUB_ADDR')
logger.info(f"Telemetry publish address: {tel_pub_addr}")
if tel_pub_addr:
    telemetry_socket.connect(tel_pub_addr)
    logger.info('Created telemetry publish endpoint')
else:
    logger.error('Cannot get telemetry publish endpoint from system')
    quit()

# Create a pub/sub socket that the camera stream can be read from
camera_socket = context.socket(zmq.PUB)
camera_socket.setsockopt(zmq.CONFLATE, 1)
cam_pub_addr = 'tcp://' + os.environ.get('STEELEAGLE_DRIVER_CAM_PUB_ADDR')
if cam_pub_addr:
    camera_socket.connect(cam_pub_addr)
    logger.info('Created camera publish endpoint')
else:
    logger.error('Cannot get camera publish endpoint from system')
    quit()




async def camera_stream(drone, camera_sock):
    frame_id = 0
    cam_message = cnc_protocol.Frame() 
    while drone.isConnected():
        try:
            cam_message.data = await drone.getVideoFrame()
            cam_message.height = 720
            cam_message.width = 1280
            cam_message.channels = 3
            cam_message.id = frame_id
            frame_id = frame_id + 1 
            camera_sock.send(cam_message.SerializeToString())
            logger.debug('Camera stream: Timestamp: {:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now()))
            logger.debug(f'Camera stream: ID: frame_id {frame_id}')
        except Exception as e:
            pass
        await asyncio.sleep(0)

async def telemetry_stream(drone, telemetry_sock):
    logger.info('Starting telemetry stream')
    tel_message = cnc_protocol.Telemetry()
    while drone.isConnected():
        try:
            telDict = await drone.getTelemetry()
            tel_message.global_position.latitude = telDict["gps"][0] 
            tel_message.global_position.longitude = telDict["gps"][1]
            tel_message.global_position.altitude = telDict["gps"][2]
            tel_message.relative_position.up = telDict["relAlt"]
            tel_message.mag = telDict["magnetometer"]
            tel_message.battery = telDict["battery"]
            tel_message.gimbal_attitude.yaw = telDict["gimbalAttitude"]["yaw"]
            tel_message.gimbal_attitude.pitch = telDict["gimbalAttitude"]["pitch"]
            tel_message.gimbal_attitude.roll = telDict["gimbalAttitude"]["roll"]
            tel_message.drone_attitude.yaw = telDict["attitude"]["yaw"]
            tel_message.drone_attitude.pitch = telDict["attitude"]["pitch"]
            tel_message.drone_attitude.roll = telDict["attitude"]["roll"]
            tel_message.velocity.forward_vel = telDict["imu"]["forward"]
            tel_message.velocity.right_vel = telDict["imu"]["right"]
            tel_message.velocity.up_vel = telDict["imu"]["up"]
            tel_message.satellites = telDict["satellites"]
            logger.debug(f"Telemetry: {tel_message}")
            telemetry_sock.send(tel_message.SerializeToString())
            logger.debug('Sent telemetry')
        except Exception as e:
            logger.error(f'Failed to get telemetry, error: {e}')
        await asyncio.sleep(0)

async def handle(identity, message, resp, action, resp_sock):
    try:
        match action:
            case "connectionStatus":
                resp.connectionStatus.isConnected = await drone.isConnected()
                resp.connectionStatus.wifi_rssi = await drone.getRSSI()
                resp.connectionStatus.drone_name = await drone.getName()
                resp.resp = cnc_protocol.ResponseStatus.COMPLETED
            case "takeOff":
                logger.info(f"takeoff function call started at: {time.time()}")
                await drone.takeOff()
                resp.resp = cnc_protocol.ResponseStatus.COMPLETED
                logger.info('####################################Drone Took OFF################################################################')
                logger.info(f"Hovering function call finished at: {time.time()}")
            case "land":
                logger.info(f"land function call started at: {time.time()}")
                await drone.land()
                resp.resp = cnc_protocol.ResponseStatus.COMPLETED
                logger.info('####################################Drone Landing#######################################################################')
                logger.info(f"land function call finished at: {time.time()}")
            case "rth":
                logger.info(f"rth function call started at: {time.time()}")
                await drone.rth()
                resp.resp = cnc_protocol.ResponseStatus.COMPLETED
                logger.info(f"rth function call finished at: {time.time()}")
            case "hover":
                logger.info(f"hover function call started at: {time.time()}")
                await drone.hover()
                logger.debug("hover !")
                resp.resp = cnc_protocol.ResponseStatus.COMPLETED
                logger.info(f"hover function call finished at: {time.time()}")
                
            case "setHome":
                location  = message.setHome
                await drone.setHome(location.latitude, location.longitude, location.altitude)
                resp.resp = cnc_protocol.ResponseStatus.COMPLETED
            case "getHome":
                resp.resp = cnc_protocol.ResponseStatus.NOTSUPPORTED
            case "setAttitude":
                attitude = message.setAttitude
                await drone.setAttitude(attitude.roll, attitude.pitch,
                    attitude.thrust, attitude.yaw)
                resp.resp = cnc_protocol.ResponseStatus.COMPLETED
            case "setVelocity":
                velocity = message.setVelocity
                logger.debug(f"Setting velocity: {velocity}")
                await drone.setVelocity(velocity.forward_vel, velocity.right_vel, velocity.up_vel, velocity.angle_vel)
                resp.resp = cnc_protocol.ResponseStatus.COMPLETED
            case "setRelativePosition":
                resp.resp = cnc_protocol.ResponseStatus.NOTSUPPORTED
            case "setTranslatedPosition":
                position = message.setTranslatedPosition
                await drone.setTranslatedPosition(position.forward, position.right, position.up, position.angle)
                resp.resp = cnc_protocol.ResponseStatus.COMPLETED
            case "setGPSLocation":
                location = message.setGPSLocation
                await drone.setGPSLocation(location.latitude, location.longitude, location.altitude, location.bearing)
                resp.resp = cnc_protocol.ResponseStatus.COMPLETED
            case "getCameras":
                resp.resp = cnc_protocol.ResponseStatus.NOTSUPPORTED
            case "switchCamera":
                resp.resp = cnc_protocol.ResponseStatus.NOTSUPPORTED
    except Exception as e:
        logger.error(f'Failed to handle command, error: {e.message}')
        resp.resp = cnc_protocol.ResponseStatus.FAILED 
        
    
    resp_sock.send_multipart([identity, resp.SerializeToString()])
      

async def main(drone, camera_sock, telemetry_sock, args):
    while True:
        try:
            await drone.connect()
            logger.info('Established connection to drone, ready to receive commands!')
        except ConnectionFailedException as e:
            logger.error('Failed to connect to drone, retrying...')
            continue
        await drone.startStreaming()
        
        asyncio.create_task(camera_stream(drone, camera_sock))
        asyncio.create_task(telemetry_stream(drone, telemetry_sock))
        
        while drone.isConnected():
            try:
                message_parts = command_socket.recv_multipart(flags=zmq.NOBLOCK)
                identity = message_parts[0]
                logger.debug(f"Received identity: {identity }")  
                data = message_parts[1]
                logger.debug(f"Received data: {data}")
                # Decode message via protobuf, then execute it
                message = cnc_protocol.Driver()
                message.ParseFromString(data)
                logger.debug(f"Received message: {message}")
                action = message.WhichOneof("method")
                
                # send a okay message
                
                
                # Create a driver response message
                resp = message
                asyncio.create_task(handle(identity, message, resp, action, command_socket))
            except zmq.Again as e:
                pass
            await asyncio.sleep(0)

if __name__ == "__main__":
    asyncio.run(main(drone, camera_socket, telemetry_socket, driverArgs))
