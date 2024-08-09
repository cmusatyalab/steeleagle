import zmq
import json
import os
import sys
import asyncio
import logging
import cnc_protocol.cnc_pb2 as cnc_protocol
from drivers.olympe.parrotdrone import ConnectionFailedException, ParrotDrone, ArgumentOutOfBoundsException

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Write log messages to stdout so they are readable in Docker logs
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

context = zmq.Context()

# Create a response socket connected to the kernel
command_socket = context.socket(zmq.ROUTER)
kernel_addr = 'tcp://' + os.environ.get('STEELEAGLE_KERNEL_COMMAND_ADDR')
if kernel_addr:
    command_socket.connect(kernel_addr)
    logger.info('Connected to kernel endpoint')
else:
    logger.error('Cannot get kernel endpoint from system')
    quit()

# Create a pub/sub socket that telemetry can be read from
telemetry_socket = context.socket(zmq.PUB)
tel_pub_addr = 'tcp://' + os.environ.get('STEELEAGLE_DRIVER_TEL_PUB_ADDR')
if tel_pub_addr:
    telemetry_socket.bind(tel_pub_addr)
    logger.info('Created telemetry publish endpoint')
else:
    logger.error('Cannot get telemetry publish endpoint from system')
    quit()

# Create a pub/sub socket that the camera stream can be read from
camera_socket = context.socket(zmq.PUB)
cam_pub_addr = 'tcp://' + os.environ.get('STEELEAGLE_DRIVER_CAM_PUB_ADDR')
if cam_pub_addr:
    camera_socket.bind(cam_pub_addr)
    logger.info('Created camera publish endpoint')
else:
    logger.error('Cannot get camera publish endpoint from system')
    quit()

driverArgs = json.loads(os.environ.get('STEELEAGLE_DRIVER_ARGS'))
droneArgs = json.loads(os.environ.get('STEELEAGLE_DRONE_ARGS'))
drone = ParrotDrone(**droneArgs)

async def camera_stream(drone, camera_sock):
    cam_message = cnc_protocol.Frame() 
    while drone.isConnected():
        try:
            cam_message.data = await drone.getVideoFrame()
            cam_message.height = 720
            cam_message.width = 1280
            cam_message.channels = 3
            camera_sock.send(cam_message.SerializeToString())
        except Exception as e:
            pass
        await asyncio.sleep(0)

async def telemetry_stream(drone, telemetry_sock):
    tel_message = cnc_protocol.Telemetry()
    while drone.isConnected():
        try:
            telDict = await drone.getTelemetry()
            tel_message.global_position.latitude = telDict["gps"][0] 
            tel_message.global_position.longitude = telDict["gps"][1]
            tel_message.global_position.altitude = telDict["gps"][2]
            tel_message.mag = telDict["magnetometer"]
            tel_message.battery = telDict["battery"]
            tel_message.gimbal_attitude.yaw = telDict["gimbalAttitude"][0]
            tel_message.gimbal_attitude.pitch = telDict["gimbalAttitude"][1]
            tel_message.gimbal_attitude.roll = telDict["gimbalAttitude"][2]
            tel_message.attitude.yaw = telDict["attitude"][0]
            tel_message.attitude.pitch = telDict["attitude"][1]
            tel_message.attitude.roll = telDict["attitude"][2]
            tel_message.imu.xvel = telDict["imu"]["speedX"]
            tel_message.imu.yvel = telDict["imu"]["speedY"]
            tel_message.imu.zvel = telDict["imu"]["speedZ"]
            tel_message.satellites = telDict["satellites"]
            telemetry_socket.send(tel_message.SerializeToString())
        except Exception as e:
            pass
        await asyncio.sleep(0)

async def handle(message, resp, action, resp_sock):
    try:
        match action:
            case "connectionStatus":
                resp.connectionStatus.isConnected = await drone.isConnected()
                resp.connectionStatus.wifi_rssi = await drone.getRSSI()
                resp.connectionStatus.drone_name = await drone.getName()
                resp.resp = cnc_protocol.ResponseStatus.OK
            case "takeOff":
                await drone.takeOff()
                resp.resp = cnc_protocol.ResponseStatus.OK
                logger.info('Drone has taken off!')
            case "land":
                await drone.land()
                resp.resp = cnc_protocol.ResponseStatus.OK
            case "rth":
                await drone.rth()
                resp.resp = cnc_protocol.ResponseStatus.OK
            case "setHome":
                #await drone.setHome(args['lat'], args['lng'])
                resp.resp = cnc_protocol.ResponseStatus.OK
            case "getHome":
                resp.resp = cnc_protocol.ResponseStatus.NOT_SUPPORTED
            case "setAttitude":
                attitude = message.setAttitude
                await drone.setAttitude(attitude.roll, attitude.pitch,
                    attitude.gaz, attitude.omega)
                resp.resp = cnc_protocol.ResponseStatus.OK
            case "setVelocity":
                resp.resp = cnc_protocol.ResponseStatus.NOT_SUPPORTED
            case "setRelativePosition":
                resp.resp = cnc_protocol.ResponseStatus.NOT_SUPPORTED
            case "setGlobalPosition":
                #await drone.setGlobalPosition(args['lat'], args['lng'], args['alt'], args['theta'])
                resp.resp = cnc_protocol.ResponseStatus.OK
            case "setTranslatedPosition":
                #await drone.setTranslatedPosition(args['x'], args['y'], args['z'], args['theta'])
                resp.resp = cnc_protocol.ResponseStatus.OK
            case "hover":
                await drone.hover()
                resp.resp = cnc_protocol.ResponseStatus.OK
            case "getCameras":
                resp.resp = cnc_protocol.ResponseStatus.NOT_SUPPORTED
            case "switchCamera":
                resp.resp = cnc_protocol.ResponseStatus.NOT_SUPPORTED
    except Exception as e:
        logger.error(f'Failed to handle command, error: {e.message}')
        resp.resp = cnc_protocol.ResponseStatus.FAILED 
        
    try:
        resp_sock.send_mutlipart(resp.SerializeToString())
    except Exception as e:
        logger.error(f'Failed to send response, error: {e.message}')
        
    logger.info(f"Sent response: {resp.SerializeToString()}")

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
                data = command_socket.recv_multipart(flags=zmq.NOBLOCK)
                # Decode message via protobuf, then execute it
                message = cnc_protocol.Driver()
                message.ParseFromString(data)
                logger.info(f"Received message: {message}")
                action = message.WhichOneof("method")
                # Create a driver response message
                resp = message
                asyncio.create_task(handle(message, resp, action, command_socket))
            except zmq.Again as e:
                pass
            await asyncio.sleep(0)

asyncio.run(main(drone, camera_socket, telemetry_socket, driverArgs))
