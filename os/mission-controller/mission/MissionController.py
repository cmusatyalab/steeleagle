
import zmq
import asyncio
import logging
from proxy import DroneProxy
from proxy import ComputeProxy
import TaskManager


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class MissionController():
    def __init__(self):
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect("tcp://localhost:5555")
        self.isTerminated = False
        
        self.fsm = {}
        self.tm = None
        
    async def run(self):
        self.drone = DroneProxy()
        self.compute = ComputeProxy()
        
        await asyncio.sleep(0)
        try:
            self.zmq.send(req.SerializeToString())
            rep = self.zmq.recv()
            if b'No commands.' != rep:
                extras  = cnc_pb2.Extras()
                extras.ParseFromString(rep)
                if extras.cmd.rth:
                    logger.info('RTH signaled from commander')
                    self.stop_mission()
                    self.manual = False
                    asyncio.create_task(self.drone.rth())
                elif extras.cmd.halt:
                    logger.info('Killswitch signaled from commander')
                    self.stop_mission()
                    self.manual = True
                    logger.info('Manual control is now active!')
                    # Try cancelling the RTH task if it exists
                    sync(self.drone.hover())
                elif extras.cmd.script_url:
                    # Validate url
                    if validators.url(extras.cmd.script_url):
                        logger.info(f'Flight script sent by commander: {extras.cmd.script_url}')
                        self.manual = False
                        asyncio.create_task(self.executeFlightScript(extras.cmd.script_url))
                    else:
                        logger.info(f'Invalid script URL sent by commander: {extras.cmd.script_url}')
                elif self.manual:
                    if extras.cmd.takeoff:
                        logger.info(f'Received manual takeoff')
                        asyncio.create_task(self.drone.takeOff())
                    elif extras.cmd.land:
                        logger.info(f'Received manual land')
                        asyncio.create_task(self.drone.land())
                    else:
                        logger.info(f'Received manual PCMD')
                        pitch = extras.cmd.pcmd.pitch
                        yaw = extras.cmd.pcmd.yaw
                        roll = extras.cmd.pcmd.roll
                        gaz = extras.cmd.pcmd.gaz
                        gimbal_pitch = extras.cmd.pcmd.gimbal_pitch
                        logger.debug(f'Got PCMD values: {pitch} {yaw} {roll} {gaz} {gimbal_pitch}')
                        asyncio.create_task(self.drone.PCMD(roll, pitch, yaw, gaz))
                        current = await self.drone.getGimbalPitch()
                        asyncio.create_task(self.drone.setGimbalPose(0, current+gimbal_pitch , 0))
            if self.tlogfile: # Log trajectory IMU data
                speeds = await self.drone.getSpeedRel()
                fspeed = speeds["speedX"]
                hspeed = speeds["speedY"]
                self.tlogfile.write(f"{time.time()},{fspeed},{hspeed} ")
        except Exception as e:
            logger.debug(e)
    
    ######################################################## MISSION ############################################################ 
    async def start_mission(self):
        # dynamic import the fsm
        from mission.MissionCreator import MissionCreator
        
        # start the tm
        self.tm = TaskManager(self.drone, self.compute, self.fsm)
        self.tm_coroutine = asyncio.create_task(self.tm.run())
        
    
    async def end_mission(self):
        if self.tm and not self.tm_coroutine.cancelled():
            self.tm_coroutine.cancel()
            self.tm = None
            self.tm_coroutine = None
            

if __name__ == "__main__":
    mc = MissionController()
    asyncio.run(mc.run())