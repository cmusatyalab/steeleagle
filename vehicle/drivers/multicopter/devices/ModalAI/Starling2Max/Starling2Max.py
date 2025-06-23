# Interface import
from multicopter.autopilots.px4 import PX4Drone


class Starling2Max(PX4Drone):

    ''' Interface methods '''
    async def get_type(self):
        return "ModalAI Starling 2 Max"
