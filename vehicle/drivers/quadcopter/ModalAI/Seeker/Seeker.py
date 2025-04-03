# Interface import
from quadcopter.autopilots.px4 import PX4Drone

class ModalAISeekerDrone(PX4Drone):

    ''' Interface methods '''
    async def get_type(self):
        return "ModalAI Seeker"
