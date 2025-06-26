import asyncio
import logging

from swarm_controller import MissionSupervisor, PatrolArea, StaticPatrolMission

import protocol.common_pb2 as common
import protocol.controlplane_pb2 as controlplane

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class FakeSocket:
    def __init__(self):
        self.sent_msgs = []
        self.recv_count = 0

    async def send_multipart(self, msg_parts):
        logger.info(f"[FakeSocket] Sending to drone: {msg_parts}")
        self.sent_msgs.append(msg_parts)

    async def recv_multipart(self):
        # Simulate receiving COMPLETED response from drone1 only
        # Only simulate 2 responses, then hang to simulate no more data.
        if self.recv_count >= 2:
            await asyncio.sleep(9999)  # Effectively block forever
            # Alternatively, raise asyncio.CancelledError() to terminate loop for testing
            # raise asyncio.CancelledError()

        response = controlplane.Response()
        if self.recv_count == 0:
            response.resp = common.ResponseStatus.OK  # First, get assignment
        else:
            response.resp = common.ResponseStatus.COMPLETED  # Then finish

        # Always return drone1 to avoid index errors
        identity = b"drone1"
        self.recv_count += 1

        return [identity, response.SerializeToString()]


async def test_mission_supervisor_single_drone():
    logger.info("=== Test: MissionSupervisor Single Drone ===")

    patrol_area_list = await PatrolArea.load_from_file("test")
    print(f"Patrol area list: {patrol_area_list}")

    # Setup StaticPatrolMission with one drone
    mission = StaticPatrolMission(
        drone_list=["drone1"], patrol_area_list=patrol_area_list, alt=10
    )

    # Use FakeSocket for testing
    fake_socket = FakeSocket()
    supervisor = MissionSupervisor(fake_socket)

    # Start supervising (drone handler runs in background)
    await supervisor.supervise(mission, ["drone1"])

    # Allow drone handler to process a few cycles
    await asyncio.sleep(0.2)

    # Print sent messages
    logger.info(f"Sent messages count: {len(fake_socket.sent_msgs)}")
    for msg in fake_socket.sent_msgs:
        logger.info(f"Sent: {msg}")


if __name__ == "__main__":
    asyncio.run(test_mission_supervisor_single_drone())
