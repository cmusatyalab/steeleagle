
import zmq
import asyncio
import logging
from user.system_call_stubs import DroneStub
from user.system_call_stubs import ComputeStub
from user.common import TaskManager
from cnc_protocol import cnc_pb2


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class MissionController():
    def __init__(self):
        context = zmq.Context()
        self.socket = context.socket(zmq.REP)
        self.socket.connect("tcp://localhost:5000")
        self.isTerminated = False
        self.tm = None
        self.transitMap = {}
        self.task_arg_map = {}
            
        
    ######################################################## MISSION ############################################################ 
    def start_mission(self):
        # dynamic import the fsm
        from user.project.Mission import Mission
        Mission.define_mission(self.transitMap, self.task_arg_map)
        
        # start the tm
        self.tm = TaskManager(self.drone, self.compute, self.transitMap, self.task_arg_map)
        self.tm_coroutine = asyncio.create_task(self.tm.run())
        
    
    def end_mission(self):
        if self.tm and not self.tm_coroutine.cancelled():
            self.tm_coroutine.cancel()
            self.tm = None
            self.tm_coroutine = None
            
        
    ######################################################## MAIN LOOP ############################################################             
    async def run(self):
        self.drone = DroneStub()
        # self.compute = ComputeStub()
        
        await asyncio.sleep(0)
        while True:
            # Receive a message
            message = self.socket.recv()

            # Parse the message based on expected type
            try:
                # For example, if expecting a Command message
                mission_command = cnc_pb2.Mission()
                mission_command.ParseFromString(message)
                print(f"Received Command: {mission_command}")
                if mission_command.startMission:
                    self.start_mission()
                    response = "Mission started"
                elif mission_command.stopMission:
                    self.end_mission()
                    response = "Mission stopped"
                else:
                    response = "Unknown command"

                # Send a reply back to the client
                self.socket.send_string(response)

            except Exception as e:
                print(f"Failed to parse message: {e}")
                self.socket.send_string("Error processing command")
            

if __name__ == "__main__":
    mc = MissionController()
    asyncio.run(mc.run())