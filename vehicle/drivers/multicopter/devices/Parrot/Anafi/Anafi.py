# General imports
import asyncio
from asyncio import futures
import logging
import grpc

# SDK imports
from multicopter.shared.parrot_olympe import ParrotOlympeDrone
from olympe.messages.gimbal import attitude

# Protocol imports
from steeleagle_sdk.protocol.services import control_service_pb2_grpc

# Utility imports
from util.config import query_config
from util.log import setup_logging
from util.cleanup import register_cleanup_handler

setup_logging()
logger = logging.getLogger("driver/Anafi")
class Anafi(ParrotOlympeDrone):

    def __init__(self, drone_id, **kwargs):
        super().__init__(drone_id, **kwargs)
        self._forward_pid_values = {"Kp": 0.3, "Kd": 10.0, "Ki": 0.001, "PrevI": 0.0, "MaxI": 10.0}
        self._right_pid_values = {"Kp": 0.3, "Kd": 10.0, "Ki": 0.001, "PrevI": 0.0, "MaxI": 10.0}
        self._up_pid_values = {"Kp": 2.0, "Kd": 10.0, "Ki": 0.0, "PrevI": 0.0, "MaxI": 10.0}
        self.type = "Parrot Anafi"

    ''' ACK methods '''
    def _is_gimbal_pose_reached(self, yaw, pitch, roll):
        # Only await on pitch/roll since the Anafi gimbal cannot yaw
        if self._drone(attitude(
            pitch_relative=pitch,
            roll_relative=roll,
            _policy="check",
            _float_tol=(1e-3, 1e-1))):
            return True
        return False
  
async def main():
    register_cleanup_handler()
    server = grpc.aio.server(
        migration_thread_pool=futures.ThreadPoolExecutor(max_workers=10)
    )
    control_service_pb2_grpc.add_ControlServicer_to_server(
        Anafi("Anafi"), server
    )
    server.add_insecure_port(query_config("internal.services.driver"))
    await server.start()
    logger.info("Services started!")

    try:
        await server.wait_for_termination()
    except (SystemExit, asyncio.exceptions.CancelledError):
        logger.info("Shutting down...")
        await server.stop(1)


if __name__ == "__main__":
    asyncio.run(main())  
