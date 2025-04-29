import time
import zmq
import zmq.asyncio
import asyncio
import importlib
import logging
import controlplane_pb2 as control_protocol
import common_pb2 as common_protocol
from util.utils import setup_socket, query_config, setup_logging, SocketOperation

logger = logging.getLogger(__name__)

class Driver:
    def __init__(self, drone):
        self.drone = drone
        self.context = zmq.asyncio.Context()
        self.hub_to_driver_sock = self.context.socket(zmq.DEALER)
        self.tel_sock = self.context.socket(zmq.PUB)
        self.cam_sock = self.context.socket(zmq.PUB)

        self.tel_sock.setsockopt(zmq.CONFLATE, 1)
        self.cam_sock.setsockopt(zmq.CONFLATE, 1)

        setup_socket(self.tel_sock, SocketOperation.CONNECT, 'hub.network.dataplane.driver_to_hub.telemetry')
        setup_socket(self.cam_sock, SocketOperation.CONNECT, 'hub.network.dataplane.driver_to_hub.image_sensor')
        setup_socket(self.hub_to_driver_sock, SocketOperation.CONNECT, 'hub.network.controlplane.hub_to_driver')

    async def run(self):
        setup_logging(logger, 'driver.logging')
        while True:
            try:
                logger.info('Attempting to connect to drone...')
                await self.drone.connect(connection_string)
                logger.info('Drone connected')
            except Exception:
                logger.error('Failed to connect to drone, retrying...')
                await asyncio.sleep(3)
                continue

            logger.info('Established connection to drone, ready to receive commands!')

            logger.info('Started streaming telemetry and video')
            asyncio.create_task(self.drone.stream_video(self.cam_sock, 5))
            asyncio.create_task(self.drone.stream_telemetry(self.tel_sock, 5))

            while await self.drone.is_connected():
                try:
                    message_parts = await self.hub_to_driver_sock.recv_multipart()
                    logger.info('Received message!')
                    identity = message_parts[0]
                    logger.info(f'Identity: {identity}')
                    data = message_parts[1]
                    logger.info(f'Data: {data}')
                    message = control_protocol.Request()
                    message.ParseFromString(data)
                    logger.info(f'Message: {message}')
                    asyncio.create_task(self.handle(identity, message, self.hub_to_driver_sock))
                except Exception as e:
                    logger.error(f'Command received error: {e}')

            logger.info('Disconnected from drone')

    async def handle(self, identity, message, resp_sock):
        if not message.HasField("veh"):
            logger.info("Received message without vehicle field, ignoring!")
            return

        # Create a driver response message
        resp = control_protocol.Response()
        vehicle_control = message.veh.WhichOneof("param")
        seq_num = message.seq_num

        try:
            result = common_protocol.ResponseStatus.UNKNOWN_RESPONSE
            if vehicle_control == "action":
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
                    result = await self.drone.hover()
                    logger.info(f"Call finished at: {time.time()}")
                elif action == control_protocol.VehicleAction.KILL:
                    logger.info('****** Emergency Kill ******')
                    logger.info(f"Call started at: {time.time()}, seq id {seq_num}")
                    result = await self.drone.kill()
                    logger.info(f"Call finished at: {time.time()}")
            elif vehicle_control == "location":
                logger.info('****** Set Global Position ******')
                logger.info(f"Call started at: {time.time()}, seq id {seq_num}")
                location = message.veh.location
                result = await self.drone.set_global_position(location)
                logger.info(f"Call finished at: {time.time()}")
            elif vehicle_control == "position_enu":
                logger.info('****** Set Position ENU ******')
                # TODO: Implement this
                logger.error('Not implemented yet!')
            elif vehicle_control == "position_enu":
                logger.info('****** Set Position ENU ******')
                # TODO: Implement this
                logger.error('Not implemented yet!')
            elif vehicle_control == "velocity_enu":
                logger.info('****** Set Velocity ENU ******')
                logger.info(f"Call started at: {time.time()}, seq id {seq_num}")
                velocity = message.veh.velocity_enu
                result = await self.drone.set_velocity_enu(velocity)
                logger.info(f"Call finished at: {time.time()}")
            elif vehicle_control == "velocity_body":
                logger.info('****** Set Velocity Body ******')
                logger.info(f"Call started at: {time.time()}, seq id {seq_num}")
                velocity = message.veh.velocity_body
                result = await self.drone.set_velocity_body(velocity)
                logger.info(f"Call finished at: {time.time()}")
            else:
                raise Exception(f"Command type {vehicle_control} is not supported!")
        except Exception as e:
            logger.error(f'Failed to handle command, error: {e}')
            result = common_protocol.ResponseStatus.FAILED

        # resp.timestamp = Timestamp()
        resp.seq_num = seq_num
        resp.resp = result
        logger.info("Sending back message")
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
    setup_logging(logger, 'driver.logging')

    drone_id = query_config('driver.id')
    drone_module = query_config('driver.module')
    drone_args = query_config('driver.keyword_args')
    connection_string = query_config('driver.connection_string')

    logger.info(f"Drone ID: {drone_id}")
    logger.info(f"Drone type: {drone_module}")
    logger.info(f"Connection string: {connection_string}")

    drone = get_drone(drone_id, drone_args, drone_module)
    driver = Driver(drone)
    asyncio.run(driver.run())
