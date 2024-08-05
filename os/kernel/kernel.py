import zmq
import json
import os
import cnc_protocol
import asyncio
import logging

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

# Create a pub/sub socket that telemetry can be read from
telemetry_socket = context.socket(zmq.PUB)
tel_pub_addr = 'udp://' + os.environ.get('STEELEAGLE_DRIVER_TEL_PUB_ADDR')
if tel_pub_addr:
    telemetry_socket.connect(tel_pub_addr)
    logger.info('Connected to telemetry publish endpoint')
else:
    logger.error('Cannot get telemetry publish endpoint from system')
    quit()

# Create a pub/sub socket that the camera stream can be read from
camera_socket = context.socket(zmq.PUB)
cam_pub_addr = 'udp://' + os.environ.get('STEELEAGLE_DRIVER_CAM_PUB_ADDR')
if cam_pub_addr:
    camera_socket.connect(cam_pub_addr)
    logger.info('Connected to camera publish endpoint')
else:
    logger.error('Cannot get camera publish endpoint from system')
    quit()


