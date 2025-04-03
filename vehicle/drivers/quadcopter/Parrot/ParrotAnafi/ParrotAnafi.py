# Interface import
from quadcopter.autopilots.parrot_olympe import ParrotOlympeDrone

class ParrotAnafiDrone(ParrotOlympeDrone):

    ''' Interface methods '''
    async def get_type(self):
        return "Parrot Anafi"
