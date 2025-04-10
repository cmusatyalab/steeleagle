import common
import time
import zmq
import zmq.asyncio
import json
import os
import asyncio
import importlib
import logging
import controlplane_pb2 as control_protocol
import common_pb2 as common_protocol
import dataplane_pb2 as data_protocol
from util.utils import setup_socket, SocketOperation, import_config
from google.protobuf.timestamp_pb2 import Timestamp

logger = logging.getLogger(__name__)

# telemetry_logger = logging.getLogger('telemetry')
# telemetry_handler = logging.FileHandler('telemetry.log')
# formatter = logging.Formatter(logging_format)
# telemetry_handler.setFormatter(formatter)
# telemetry_logger.handlers.clear()
# telemetry_logger.addHandler(telemetry_handler)
# telemetry_logger.propagate = False

class Driver:
    def __init__(self, drone, config):
        self.drone = drone
        self.context = zmq.asyncio.Context()
        self.cmd_back_sock = self.context.socket(zmq.DEALER)
        self.tel_sock = self.context.socket(zmq.PUB)
        self.cam_sock = self.context.socket(zmq.PUB)

        self.tel_sock.setsockopt(zmq.CONFLATE, 1)
        self.cam_sock.setsockopt(zmq.CONFLATE, 1)

        hub_config = config.get('hub')
        if hub_config is None:
            raise Exception("Hub config not specified")

        data_endpoint = hub_config.get("data_endpoint")
        if data_endpoint is None:
            raise Exception("Data endpoint not specified")

        command_endpoint = hub_config.get("command_endpoint")
        if command_endpoint is None:
            raise Exception("Command endpoint not specified")

        port_config = hub_config.get('ports')
        data_ports = port_config.get('data_port')
        if data_ports is None:
            raise Exception('Data ports not specified')

        driver_to_data_ports = data_ports.get('driver_to_hub')
        if driver_to_data_ports is None:
            raise Exception('Driver to data ports not specified')

        hub_to_mission_ports = data_ports.get('hub_to_mission')
        if hub_to_mission_ports is None:
            raise Exception('Hub to mission ports not specified')

        command_ports = port_config.get('command_port')
        if command_ports is None:
            raise Exception('Command ports not specified')

        tel_port = driver_to_data_ports.get('telemetry')
        cam_port = driver_to_data_ports.get('image_sensor')
        cmd_port = command_ports.get('hub_to_driver')

        setup_socket(self.tel_sock, SocketOperation.CONNECT, tel_port, data_endpoint)
        setup_socket(self.cam_sock, SocketOperation.CONNECT, cam_port, data_endpoint)
        setup_socket(self.cmd_back_sock, SocketOperation.CONNECT, cmd_port, command_endpoint)

    async def run(self):
        while True:
            try:
                logger.info('Attempting to connect to drone...')
                await self.drone.connect(connection_string)
                logger.info('Drone connected')
            except Exception as e:
                logger.error('Failed to connect to drone, retrying...')
                await asyncio.sleep(3)
                continue

            logger.info(f'Established connection to drone, ready to receive commands!')

            logger.info('Started streaming telemetry and video')
            asyncio.create_task(self.drone.stream_video(self.cam_sock, 5))
            asyncio.create_task(self.drone.stream_telemetry(self.tel_sock, 5))

            while await self.drone.is_connected():
                try:
                    message_parts = await self.cmd_back_sock.recv_multipart()
                    logger.info(f'Received message!')
                    identity = message_parts[0]
                    logger.info(f'Identity: {identity}')
                    data = message_parts[1]
                    logger.info(f'Data: {data}')
                    message = control_protocol.Request()
                    message.ParseFromString(data)
                    logger.info(f'Message: {message}')
                    asyncio.create_task(self.handle(identity, message, cmd_back_sock))
                except Exception as e:
                    logger.error(f'Command received error: {e}')

            logger.info('Disconnected from drone')

    async def handle(self, identity, message, resp_sock):
        if not message.HasField("veh"):
            logger.info("Received message without vehicle field, ignoring!")
            return

        # Create a driver response message
        resp = control_protocol.Response()
        man_control = message.veh.WhichOneof("param")
        seq_num = message.seq_num

        try:
            result = common_protocol.ResponseStatus.UNKNOWN_RESPONSE
            if man_control == "action":
                action = message.veh.action
                if action == control_protocol.VehicleAction.TAKEOFF:
                    logger.info('****** Takeoff ******')
                    logger.info(f"Call started at: {time.time()}, seq id {seq_num}")
                    result  = await self.drone.take_off()
                    logger.info(f"Call finished at: {time.time()}")
                elif action == control_protocol.VehicleAction.LAND:
                    logger.info('****** Land ******')
                    logger.info(f"Call started at: {time.time()}, seq id {seq_num}")
                    result  = await self.drone.land()
                    logger.info(f"Call finished at: {time.time()}")
                elif action == control_protocol.VehicleAction.RTH:
                    logger.info('****** Return to Home ******')
                    logger.info(f"Call started at: {time.time()}, seq id {seq_num}")
                    result  = await self.drone.rth()
                    logger.info(f"Call finished at: {time.time()}")
                elif action == control_protocol.VehicleAction.HOVER:
                    logger.info('****** Hover ******')
                    logger.info(f"Call started at: {time.time()}, seq id {seq_num}")
                    result  = await self.drone.rth()
                    result = await self.drone.hover()
                    logger.info(f"Call finished at: {time.time()}")
                elif action == control_protocol.VehicleAction.KILL:
                    logger.info('****** Emergency Kill ******')
                    logger.info(f"Call started at: {time.time()}, seq id {seq_num}")
                    result = await self.drone.kill()
                    logger.info(f"Call finished at: {time.time()}")
            elif man_control == "velocity":
                logger.info('****** Set Velocity ******')
                logger.info(f"Call started at: {time.time()}, seq id {seq_num}")
                velocity = message.veh.velocity
                result = await self.drone.set_velocity(velocity)
                logger.info(f"Call finished at: {time.time()}")
            elif man_control == "location":
                logger.info('****** Set Global Position ******')
                logger.info(f"Call started at: {time.time()}, seq id {seq_num}")
                location = message.veh.location
                result = await self.drone.set_global_position(location)
                logger.info(f"Call finished at: {time.time()}")
        except Exception as e:
            logger.error(f'Failed to handle command, error: {e}')
            result = common_protocol.ResponseStatus.FAILED

        # resp.timestamp = Timestamp()
        resp.seq_num = seq_num
        resp.resp = result
        resp_sock.send_multipart([identity, resp.SerializeToString()])

def get_drone(drone_id, drone_args, drone_module):
    try:
        drone_name = drone_module.split('.')[-1]
        drone_import = f"multicopter.{drone_module}.{drone_name}"
        drone_obj = importlib.import_module(drone_import)
        drone = getattr(drone_obj, drone_name)(drone_id, **drone_args)
        return drone
    except Exception as e:
        raise Exception(f"Could not initialize drone, reason: {e}")

if __name__ == "__main__":
    config_path = os.getenv("CONFIG_PATH")
    if config_path is None:
        raise Exception("Expected CONFIG_PATH env variable to be specified")

    config = import_config(config_path)
    driver_config = config.get("driver")
    if driver_config is None:
        raise Exception("Driver config not available")

    logging_config = driver_config.get('logging')
    common.setup_logging(logger, logging_config)

    drone_id = driver_config.get("id")
    drone_module = driver_config.get("module")
    drone_args = driver_config.get("keyword_args")
    connection_string = driver_config.get("connection_string")

    logger.info(f"Drone ID: {drone_id}")
    logger.info(f"Drone type: {drone_module}")
    logger.info(f"Connection string: {connection_string}")

    drone = get_drone(drone_id, drone_args, drone_module)
    driver = Driver(drone, config)
    
    asyncio.run(driver.run())
