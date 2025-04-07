import time
import zmq
import zmq.asyncio
import json
import os
import asyncio
import logging
from protocol import controlplane_pb2 as control_protocol
from protocol import common_pb2 as common_protocol
from protocol import dataplane_pb2 as data_protocol
from util.utils import setup_socket, SocketOperation
from google.protobuf.timestamp_pb2 import Timestamp

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

drone = None
if drone_type == 'SkyViper2450GPS':
    from quadcopter.SkyRocket.SkyViperV2450GPS.SkyViperV2450GPS import SkyViperV2450GPSDrone
    drone = SkyViperV2450GPSDrone(drone_id)
elif drone_type == 'Anafi':
    from quadcopter.Parrot.Anafi.Anafi import AnafiDrone
    drone = AnafiDrone(drone_id)
elif drone_type == 'Starling2Max':
    from quadcopter.ModalAI.Starling2Max.Starling2Max import Starling2MaxDrone
    drone = Starling2MaxDrone(drone_id)
elif drone_type == 'Seeker':
    from quadcopter.ModalAI.Seeker.Seeker import Seeker
    drone = SeekerDrone(drone_id)
    
context = zmq.asyncio.Context()
cmd_back_sock = context.socket(zmq.DEALER)
tel_sock = context.socket(zmq.PUB)
cam_sock = context.socket(zmq.PUB)
tel_sock.setsockopt(zmq.CONFLATE, 1)
cam_sock.setsockopt(zmq.CONFLATE, 1)
setup_socket(tel_sock, SocketOperation.CONNECT, 'TEL_PORT', 'Created telemetry socket endpoint', os.environ.get("DATA_ENDPOINT"))
setup_socket(cam_sock, SocketOperation.CONNECT, 'CAM_PORT', 'Created camera socket endpoint', os.environ.get("DATA_ENDPOINT"))
setup_socket(cmd_back_sock, SocketOperation.CONNECT, 'CMD_BACK_PORT', 'Created command backend socket endpoint', os.environ.get("CMD_ENDPOINT"))

async def handle(identity, message, resp_sock):
    if not message.HasField("veh"):
        logger.info("Received message without vehicle field, ignoring")
        return
    
    # Create a driver response message
    resp = control_protocol.Response()
    
    man_control = message.veh.WhichOneof("param")
    logger.info(f"man_control: {man_control}")
    seq_num = message.seq_num
    
    try:
        result = common_protocol.ResponseStatus.UNKNOWN_RESPONSE
        if man_control == "action":
            action = message.veh.action
            if action == control_protocol.VehicleAction.TAKEOFF:
                logger.info(f"takeoff function call started at: {time.time()}, seq id {seq_num}")
                logger.info('####################################Taking OFF################################################################')
                result  = await drone.take_off()
                logger.info(f"tookoff function call finished at: {time.time()}")
            elif action == control_protocol.VehicleAction.LAND:
                logger.info(f"land function call started at: {time.time()}, seq id {seq_num}")
                logger.info('####################################Landing#######################################################################')
                result  = await drone.land()
                logger.info(f"land function call finished at: {time.time()}")
            elif action == control_protocol.VehicleAction.RTH:
                logger.info(f"rth function call started at: {time.time()}, seq id {seq_num}")
                logger.info('####################################Returning to Home#######################################################################')
                result  = await drone.rth()
                logger.info(f"rth function call finished at: {time.time()}")
            elif action == control_protocol.VehicleAction.HOVER: 
                logger.info(f"hover function call started at: {time.time()}, seq id {seq_num}")
                logger.info('####################################Hovering#######################################################################')
                result = await drone.hover()
                logger.info(f"hover function call finished at: {time.time()}")
            elif action == control_protocol.VehicleAction.KILL:
                logger.info(f"kill function call started at: {time.time()}, seq id {seq_num}") 
                result = await drone.kill() 
                logger.info(f"kill function call finished at: {time.time()}")
        elif man_control == "velocity":
            logger.info(f"setVelocity function call started at: {time.time()}, seq id {seq_num}")
            logger.info('####################################Setting Velocity#######################################################################')
            velocity = message.veh.velocity
            result = await drone.set_velocity(velocity)
            logger.info(f"setVelocity function call finished at: {time.time()}")
        elif man_control == "location":
            logger.info(f"setGPSLocation function call started at: {time.time()}")
            logger.info('####################################Setting GPS Location#######################################################################')
            location = message.veh.location
            result = await drone.set_global_position(location)
            logger.info(f"setGPSLocation function call finished at: {time.time()}")
    except Exception as e:
        logger.error(f'Failed to handle command, error: {e}')
        result = common_protocol.ResponseStatus.FAILED
    
    # resp.timestamp = Timestamp()
    resp.seq_num = seq_num
    resp.resp = result
    resp_sock.send_multipart([identity, resp.SerializeToString()])


async def main(drone, cam_sock, tel_sock, args):
    while True:
        try:
            logger.info('starting connecting...')
            await drone.connect(connection_string)
            logger.info('drone connected')
        except Exception as e:
            logger.error('Failed to connect to drone, retrying...')
            await asyncio.sleep(3)
            continue
        logger.info(f'Established connection to drone, ready to receive commands!')
        
        logger.info('Started streaming')
        # asyncio.create_task(drone.stream_video(cam_sock))
        asyncio.create_task(drone.stream_telemetry(tel_sock))

        while await drone.is_connected():
            try:
                message_parts = await cmd_back_sock.recv_multipart()
                identity = message_parts[0]
                logger.info(f"Received identity: {identity}")
                data = message_parts[1]
                logger.info(f"Received data: {data}")
                message = control_protocol.Request()
                message.ParseFromString(data)
                logger.info(f"Received message: {message}")
                asyncio.create_task(handle(identity, message, cmd_back_sock))
            except Exception as e:
                logger.info(f'cmd received error: {e}')

        logger.info(f"Disconnected from drone")

if __name__ == "__main__":
    asyncio.run(main(drone, cam_sock, tel_sock, driverArgs))
