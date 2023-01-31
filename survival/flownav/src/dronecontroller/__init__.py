import rospy
from geometry_msgs.msg import Twist  	 # for sending commands to the drone
from std_msgs.msg import Empty       	 # for land/takeoff/emergency
from ardrone_autonomy.msg import Navdata # for receiving navdata feedback
from operator import itemgetter
from collections import OrderedDict

MAX_SPEED=1
STEP = 0.1

DroneStatus = OrderedDict(Emergency = 0
                   ,Inited = 1
                   ,Landed = 2
                   ,Flying = 3
                   ,Hovering = 4
                   ,Test = 5
                   ,TakingOff = 6
                   ,GotoHover = 7
                   ,Landing = 8
                   ,Looping = 9)


class DroneController(object):
    """
    Thanks to Mike Hammer for providing the base for this class. His code can be
    found at: https://github.com/mikehamer/ardrone_tutorials
    """
    def __init__(self,max_speed=0.5,cmd_period=100):
        self._current_state = dict(roll=0,pitch=0,z_velocity=0,yaw_velocity=0)
        self._last_state = self._current_state.copy()
        self._queue = []

        self.navdata=Navdata()
        self.subNavdata = rospy.Subscriber('/ardrone/navdata',Navdata,lambda data: setattr(self,'navdata',data))

        self.pubLand    = rospy.Publisher('/ardrone/land',Empty,queue_size=1)
        self.pubTakeoff = rospy.Publisher('/ardrone/takeoff',Empty,queue_size=1)
        self.pubReset   = rospy.Publisher('/ardrone/reset',Empty,queue_size=1)
        self.pubCommand = rospy.Publisher('/cmd_vel',Twist,queue_size=30)

        self.commandTimer = rospy.Timer(rospy.Duration(cmd_period/1000.0),self.__PublishCommand)
        self.max_speed = min(abs(max_speed),MAX_SPEED)

        rospy.on_shutdown(self.SendLand)
    
    def SendTakeoff(self):
        # Send a takeoff message to the ardrone driver. Note we only
        # send a takeoff message if the drone is landed - an unexpected
        # takeoff is not good!
        if self.navdata.state == DroneStatus["Landed"]:
                self.pubTakeoff.publish(Empty())

    def SendLand(self):
        # Send a landing message to the ardrone driver
        # Note we send this in all states, landing can do no harm
        self.pubLand.publish(Empty())

    def SendEmergency(self):
        self.pubReset.publish(Empty())

    def SendCommand(self,pitch=None,roll=None,z_velocity=None,yaw_velocity=None,ncycles=1,relative=False):
        if ncycles==0: return

        # update the state dictionary (only variables that were set)
        cmdargs = dict(pitch=pitch,roll=roll,z_velocity=z_velocity,yaw_velocity=yaw_velocity)
        if any(v is not None for v in cmdargs.values()):
            self._current_state.update([ (k , self.__saturate( (v+self._current_state[k]) if relative else v ))
                                         for k,v in cmdargs.items() if v is not None])
        
        cmd = Twist()
        cmd.linear.x  = self._current_state['pitch']
        cmd.linear.y  = self._current_state['roll']
        cmd.linear.z  = self._current_state['z_velocity']
        cmd.angular.z = self._current_state['yaw_velocity']
        self._queue.append(cmd)

        self.SendCommand(ncycles=ncycles-1)

    def __PublishCommand(self,event):
        if self.navdata.state in itemgetter("Flying","GotoHover","Hovering")(DroneStatus):
            # if nothing is left in the queue, just repeat the current state
            if len(self._queue) == 0: self.SendCommand()
            self.pubCommand.publish(self._queue.pop())

    def __saturate(self,val):
        return self.max_speed if val > self.max_speed else (-self.max_speed if val < -self.max_speed else val)

    def close(self):
        self.SendLand()
