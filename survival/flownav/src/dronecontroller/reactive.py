from . import DroneController,STEP


class ReactiveController(DroneController):
    def RollLeft(self):
        self.SendCommand(roll = 2*STEP, ncycles=10)
        self.SendCommand(roll = 0)

    def RollRight(self):
        self.SendCommand(roll = -2*STEP, ncycles=10)
        self.SendCommand(roll = 0)

    def TurnLeft(self):
        self.SendCommand(yaw_velocity = 2*STEP, ncycles=10)
        self.SendCommand(yaw_velocity = 0)

    def TurnRight(self):
        self.SendCommand(yaw_velocity = -2*STEP, ncycles=10)
        self.SendCommand(yaw_velocity = 0)
        
    def Pause(self):
        self._last_state.update(self._current_state)
        self.SendCommand(pitch=0)

    def Play(self):
        self._current_state.update(self._last_state)
        if self._current_state['pitch'] == 0:
            self.SendTakeoff()
            self.SendCommand(pitch=STEP)

    # def React(self,keypoints,img):
    #     if not keypoints: return

    #     filtkps = [kp for kp in keypoints if kp.detects > 1]

    #     print zip(filtkps,attrgetter('scalehist')(filtkps))

    #     x_obs = avgKP(filtkps)
    #     if x_obs < img.shape[1]//2: self.RollRight()
    #     if x_obs >= img.shape[1]//2: self.RollLeft()

if __name__=='__main__':
    rospy.init_node('ardrone/reactive_controller')

    autoctrl = ReactiveController()

    rospy.spin()
