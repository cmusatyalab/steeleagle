import zmq
import json
import os
import sys
import asyncio
import logging
from parrotdrone import ParrotDrone, ArgumentOutOfBoundsException

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Write log messages to stdout so they are readable in Docker logs
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
root.addHandler(handler)

context = zmq.Context()

# Create a response socket connected to the kernel
command_socket = context.socket(zmq.REP)
kernel_addr = 'tcp://' + os.environ.get('STEELEAGLE_KERNEL_COMMAND_ADDR')
if kernel_addr:
    command_socket.connect(kernel_addr)
    logger.info('Connected to kernel endpoint')
else:
    logger.error('Cannot get kernel endpoint from system')
    quit()

# Create a pub/sub socket that telemetry can be read from
telemetry_socket = context.socket(zmq.PUB)
tel_pub_addr = 'udp://' + os.environ.get('STEELEAGLE_DRIVER_TEL_PUB_ADDR')
if tel_pub_addr:
    telemetry_socket.bind(tel_pub_addr)
    logger.info('Created telemetry publish endpoint')
else:
    logger.error('Cannot get telemetry publish endpoint from system')
    quit()

# Create a pub/sub socket that the camera stream can be read from
camera_socket = context.socket(zmq.PUB)
cam_pub_addr = 'udp://' + os.environ.get('STEELEAGLE_DRIVER_CAM_PUB_ADDR')
if cam_pub_addr:
    camera_socket.bind(cam_pub_addr)
    logger.info('Created camera publish endpoint')
else:
    logger.error('Cannot get camera publish endpoint from system')
    quit()

driverArgs = json.loads(os.environ.get('STEELEAGLE_DRIVER_ARGS'))
droneArgs = json.loads(os.environ.get('STEELEAGLE_DRONE_ARGS'))
drone = ParrotDrone(**droneArgs)

async def main(droneRef, args):
    while True:
        try:
            await drone.connect()
            logger.info('Established connection to drone, ready to receive commands!')
        except ConnectionFailedException as e:
            logger.error('Failed to connect to drone, retrying...')
            continue
        await drone.startStreaming()
        while drone.isConnected():
            try:
                message = command_socket.recv(flags=zmq.NOBLOCK)
                # Decode message via protobuf, then execute it
                action = None
                args = None
                resp = None

                match action:
                    case "getConnectionStatus":
                        #TODO
                    case "takeoff":
                        asyncio.create_task(drone.takeOff())
                    case "land":
                        asyncio.create_task(drone.land())
                    case "rth":
                        asyncio.create_task(drone.rth())
                    case "setHome":
                        asyncio.create_task(drone.setHome(args['lat'], args['lng']))
                    case "getHome":
                        #TODO
                    case "setAttitude":
                        #TODO: Create a subtask that constantly sends setpoints when not in manual mode
                    case "setVelocity":
                        #TODO: Return unimplemented
                    case "setRelativePosition":
                        #TODO: Return unimplemented
                    case "setGlobalPosition":
                        asyncio.create_task(drone.setGlobalPosition(args['lat'], args['lng'], args['alt'], args['theta']))
                    case "setTranslatedPosition":
                        asyncio.create_task(drone.setTranslatedPosition(args['x'], args['y'], args['z'], args['theta']))
                    case "hover":
                        asyncio.create_task(drone.hover())
                    case "getCameras":
                        #TODO
                    case "switchCamera":
                        #TODO

                command_socket.send(resp)


            except zmq.Again as e:
                pass
            asyncio.sleep(0)

asyncio.run(main(drone, driverArgs))
