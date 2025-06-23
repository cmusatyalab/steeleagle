# Interface import
from multicopter.autopilots.parrot_olympe import ParrotOlympeDrone

# Olympe SDK import
from olympe.messages.gimbal import attitude


class Anafi(ParrotOlympeDrone):

    def __init__(self, drone_id, **kwargs):
        super().__init__(drone_id, **kwargs)
        self._forward_pid_values = {"Kp": 0.3, "Kd": 10.0, "Ki": 0.001, "PrevI": 0.0, "MaxI": 10.0}
        self._right_pid_values = {"Kp": 0.3, "Kd": 10.0, "Ki": 0.001, "PrevI": 0.0, "MaxI": 10.0}
        self._up_pid_values = {"Kp": 2.0, "Kd": 10.0, "Ki": 0.0, "PrevI": 0.0, "MaxI": 10.0}

    ''' Interface methods '''
    async def get_type(self):
        return "Parrot Anafi"

    ''' ACK methods '''
    def _is_gimbal_pose_reached(self, yaw, pitch, roll):
        # Only await on pitch/roll since the Anafi gimbal cannot yaw
        if self._drone(attitude(
            pitch_relative=pitch,
            roll_relative=roll,
            _policy="check",
            _float_tol=(1e-3, 1e-1))):
            return True
        return False
