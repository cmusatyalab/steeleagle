# Interface import
from multicopter.autopilots.parrot_olympe import ParrotOlympeDrone

class Anafi(ParrotOlympeDrone):

    def __init__(self, drone_id):
        super().__init__(drone_id)
        self._forward_pid_values = {"Kp": 0.4, "Kd": 5.0, "Ki": 0.001, "PrevI": 0.0, "MaxI": 10.0}
        self._right_pid_values = {"Kp": 0.4, "Kd": 5.0, "Ki": 0.001, "PrevI": 0.0, "MaxI": 10.0}
        self._up_pid_values = {"Kp": 2.0, "Kd": 10.0, "Ki": 0.0, "PrevI": 0.0, "MaxI": 10.0}

    ''' Interface methods '''
    async def get_type(self):
        return "Parrot Anafi"
