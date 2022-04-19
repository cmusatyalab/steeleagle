from drones.OlympeDrone.impl import OlympeDrone
from drones.TelloDrone.impl import TelloDrone

def get_drone(platform, **kwargs):
    if platform == 'olympe':
        return OlympeDrone(ip=kwargs['ip'])
    elif platform == 'dji':
        return TelloDrone()
    else:
        raise Exception('ERROR: Unsupported drone platform specified!')

