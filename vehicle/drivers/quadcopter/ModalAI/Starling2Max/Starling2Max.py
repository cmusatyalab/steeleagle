# Interface import
from quadcopter.autopilots.px4 import PX4Drone

class ModalAIStarling2MaxDrone(PX4Drone):

    ''' Interface methods '''
    async def get_type(self):
        return "ModalAI Starling 2 Max"
