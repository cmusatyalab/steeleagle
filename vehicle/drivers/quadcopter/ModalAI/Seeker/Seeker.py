from quadcopter.autopilots.px4 import PX4Drone

class ModalAISeekerDrone(PX4Drone):

    async def get_type(self):
        return "ModalAI Seeker"
