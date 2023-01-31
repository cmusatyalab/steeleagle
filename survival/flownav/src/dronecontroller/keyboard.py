from . import DroneController,STEP
from reactive import ReactiveController

CharMap = dict(   FlightToggle = ' '
                , StartStopToggle = '\r'
                , IncreaseVelocity = 'j'
                , DecreaseVelocity = 'k'
                , IncreaseAltitude = 'h'
                , DecreaseAltitude = 'l'
                , Emergency = 'e'
                , EvadeLeft = '<'
                , EvadeRight= '>'
                , TurnLeft = ','
                , TurnRight= '.')
KeyMapping = dict(zip(CharMap.keys(),map(ord,CharMap.values())))

class KeyboardController(ReactiveController):
    """
    Thanks to Mike Hammer for providing the base for this class. His code can be
    found at: https://github.com/mikehamer/ardrone_tutorials
    """
    def keyPressEvent(self, key):
        if key == KeyMapping['Emergency']:
            self.SendEmergency()

        elif key == KeyMapping['FlightToggle']:
            if self.navdata.state == DroneStatus["Landed"]:
                self.SendTakeoff()
            else:
                self.SendLand()

        elif key == KeyMapping['StartStopToggle']:
            if self.navdata.state in (DroneStatus['GotoHover'],DroneStatus['Hovering']):
                self.Play()
            else:
                self.Pause()

        elif key == KeyMapping['EvadeLeft']:
            self.RollLeft()
        elif key == KeyMapping['EvadeRight']:
            self.RollRight()

        elif key == KeyMapping['TurnLeft']:
            self.TurnLeft()
        elif key == KeyMapping['TurnRight']:
            self.TurnRight()

        elif key == KeyMapping['IncreaseVelocity']:
            self.SendCommand(pitch=STEP,relative=True)
        elif key == KeyMapping['DecreaseVelocity']:
            self.SendCommand(pitch=-STEP,relative=True)

        elif key == KeyMapping['IncreaseAltitude']:
            self.SendCommand(z_velocity=2*STEP,ncycles=4)
            self.SendCommand(z_velocity=0)            
        elif key == KeyMapping['DecreaseAltitude']:
            self.SendCommand(z_velocity=-2*STEP,ncycles=4)
            self.SendCommand(z_velocity=0)
