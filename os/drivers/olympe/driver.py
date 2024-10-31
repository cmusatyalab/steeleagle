import time
import zmq
import zmq.asyncio
import json
import os
import sys
import asyncio
import logging
import cnc_protocol.cnc_pb2 as cnc_protocol
from util.utils import setup_socket, SocketOperation
from parrotdrone import ParrotDrone, ConnectionFailedException, ArgumentOutOfBoundsException
from datetime import datetime
import signal

# Configure logger
logging.basicConfig(level=os.environ.get('LOG_LEVEL', logging.INFO),
                    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

driverArgs = json.loads(os.environ.get('STEELEAGLE_DRIVER_ARGS'))
droneArgs = json.loads(os.environ.get('STEELEAGLE_DRIVER_DRONE_ARGS'))
drone = ParrotDrone(**droneArgs)

context = zmq.asyncio.Context()
cmd_back_sock = context.socket(zmq.DEALER)
tel_sock = context.socket(zmq.PUB)
cam_sock = context.socket(zmq.PUB)
tel_sock.setsockopt(zmq.CONFLATE, 1)
cam_sock.setsockopt(zmq.CONFLATE, 1)
setup_socket(tel_sock, SocketOperation.CONNECT, 'TEL_PORT', 'Created telemetry socket endpoint', os.environ.get("DATA_ENDPOINT"))
setup_socket(cam_sock, SocketOperation.CONNECT, 'CAM_PORT', 'Created camera socket endpoint', os.environ.get("DATA_ENDPOINT"))
setup_socket(cmd_back_sock, SocketOperation.CONNECT, 'CMD_BACK_PORT', 'Created command backend socket endpoint', os.environ.get("CMD_ENDPOINT"))

error_frequency = int(os.environ.get('ERROR_FREQUENCY'))

def handle_signal(signum, frame):
    logger.info(f"Received signal {signum}, cleaning up...")
    drone.drone.disconnect()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


async def camera_stream(drone, cam_sock):
    logger.info('Starting camera stream')
    frame_id = 0
    error_count = 0
    while drone.isConnected():
        try:
            cam_message = cnc_protocol.Frame()
            cam_message.data = await drone.getVideoFrame()
            cam_message.height = 720
            cam_message.width = 1280
            cam_message.channels = 3
            cam_message.id = frame_id
            frame_id = frame_id + 1
            cam_sock.send(cam_message.SerializeToString())
            logger.debug(f'Camera stream: ID: frame_id {frame_id}')
        except Exception as e:
            if error_count % error_frequency == 0:
                logger.error(f'Failed to get video frame, error: {e}')
            error_count += 1
        await asyncio.sleep(0.033)
    logger.INFO("Camera stream ended, disconnected from drone")

async def telemetry_stream(drone, tel_sock):
    logger.info('Starting telemetry stream')
    error_count = 0
    while drone.isConnected():
        try:
            tel_message = cnc_protocol.Telemetry()
            telDict = await drone.getTelemetry()
            tel_message.drone_name = telDict["name"]
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
            tel_sock.send(tel_message.SerializeToString())
            logger.debug('Sent telemetry')
        except Exception as e:
            if error_count % error_frequency == 0:
                logger.error(f'Failed to get telemetry, error: {e}')
            error_count += 1
        await asyncio.sleep(0)
    logger.INFO("Telemetry stream ended, disconnected from drone")

async def handle(identity, message, resp, action, resp_sock):
    try:
        match action:
            case "connectionStatus":
                resp.connectionStatus.isConnected = await drone.isConnected()
                resp.connectionStatus.wifi_rssi = await drone.getRSSI()
                resp.connectionStatus.drone_name = await drone.getName()
                resp.resp = cnc_protocol.ResponseStatus.COMPLETED
            case "takeOff":
                logger.info(f"takeoff function call started at: {time.time()}, seq id {message.seqNum}")
                await drone.takeOff()
                resp.resp = cnc_protocol.ResponseStatus.COMPLETED
                logger.info('####################################Drone Took OFF################################################################')
                logger.info(f"tookoff function call finished at: {time.time()}")
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
                logger.debug(f"hover function call started at: {time.time()}, seq id {message.seqNum}")
                await drone.hover()
                logger.debug("hover !")
                resp.resp = cnc_protocol.ResponseStatus.COMPLETED
                logger.debug(f"hover function call finished at: {time.time()}")
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
                logger.info(f"Setting velocity: {velocity} started at {time.time()}, seq id {message.seqNum}")
                await drone.setVelocity(velocity.forward_vel, velocity.right_vel, velocity.up_vel, velocity.angle_vel)
                resp.resp = cnc_protocol.ResponseStatus.COMPLETED
            case "setGimbal":
                gimbal = message.setGimbal
                logger.info(f"Setting gimbal: {gimbal} started at {time.time()}, seq id {message.seqNum}")
                await drone.rotateGimbal(0, gimbal.pitch_theta, 0)
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


async def main(drone, cam_sock, tel_sock, args):
    while True:
        try:
            await drone.connect()
        except ConnectionFailedException as e:
            logger.error('Failed to connect to drone, retrying...')
            continue
        name = await drone.getName()
        logger.info(f'Established connection to drone {name}, ready to receive commands!')
        await drone.startStreaming()

        asyncio.create_task(camera_stream(drone, cam_sock))
        asyncio.create_task(telemetry_stream(drone, tel_sock))

        while drone.isConnected():
            try:
                message_parts = await cmd_back_sock.recv_multipart()
                identity = message_parts[0]
                logger.debug(f"Received identity: {identity}")
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
                asyncio.create_task(handle(identity, message, resp, action, cmd_back_sock))
            except Exception as e:
                logger.info(f'cmd received error: {e}')

        logger.INFO("Disconnected from drone {name})

if __name__ == "__main__":
    asyncio.run(main(drone, cam_sock, tel_sock, driverArgs))
