
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
        self.socket = context.socket(zmq.REQ)
        self.socket.connect("tcp://localhost:5555")
        self.isTerminated = False

        self.tm = None
        
        self.transitMap = {}
        self.task_arg_map = {}
            
        
    ######################################################## MISSION ############################################################ 
    async def start_mission(self):
        # dynamic import the fsm
        from mission.MissionCreator import MissionCreator
        MissionCreator.define_mission(self.transitMap, self.task_arg_map)
        
        # start the tm
        self.tm = TaskManager(self.drone, self.compute, self.transitMap, self.task_arg_map)
        self.tm_coroutine = asyncio.create_task(self.tm.run())
        
    
    async def end_mission(self):
        if self.tm and not self.tm_coroutine.cancelled():
            self.tm_coroutine.cancel()
            self.tm = None
            self.tm_coroutine = None
            
        
    ######################################################## MAIN LOOP ############################################################             
    async def run(self):
        self.drone = DroneProxy()
        self.compute = ComputeProxy()
        
        await asyncio.sleep(0)
        while True:
            # Receive a message
            message = self.socket.recv()

            # Parse the message based on expected type
            try:
                # For example, if expecting a Command message
                auto_command = cnc_pb2.AutoCommand()
                auto_command.ParseFromString(message)
                print(f"Received Command: {auto_command}")
                if auto_command.start:
                    self.start_mission()
                elif auto_command.end:
                    self.end_mission()
                    
            except Exception as e:
                print(f"Failed to parse message: {e}")
            

if __name__ == "__main__":
    mc = MissionController()
    asyncio.run(mc.run())