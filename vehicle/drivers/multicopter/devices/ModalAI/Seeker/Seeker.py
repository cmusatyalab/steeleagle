# Interface import
from multicopter.autopilots.px4 import PX4Drone

class SeekerDrone(PX4Drone):

    ''' Interface methods '''
    async def get_type(self):
        return "ModalAI Seeker"
