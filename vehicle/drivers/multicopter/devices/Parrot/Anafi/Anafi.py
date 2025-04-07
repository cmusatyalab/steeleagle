# Interface import
from multicopter.autopilots.parrot_olympe import ParrotOlympeDrone

class AnafiDrone(ParrotOlympeDrone):

    def __init__(self, drone_id):
        super().__init__(drone_id)
        self._forward_pid_values = {"Kp": 0.925, "Kd": 0.0, "Ki": 0.0, "PrevI": 0.0, "MaxI": 10.0}
        self._right_pid_values = {"Kp": 0.925, "Kd": 0.0, "Ki": 0.0, "PrevI": 0.0, "MaxI": 10.0}
        self._up_pid_values = {"Kp": 2.5, "Kd": 1.5, "Ki": 0.0, "PrevI": 0.0, "MaxI": 10.0}

    ''' Interface methods '''
    async def get_type(self):
        return "Parrot Anafi"
