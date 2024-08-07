
import sys
import zmq
import asyncio
import logging
from user.system_call_stubs.DroneStub import DroneStub
from user.system_call_stubs.ComputeStub import ComputeStub
from user.common.TaskManager import TaskManager
from cnc_protocol import cnc_pb2


logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class MissionController():
    def __init__(self):
        context = zmq.Context()
        self.socket = context.socket(zmq.REP)
        self.socket.bind("tcp://*:5000") 
        self.isTerminated = False
        self.tm = None
        self.transitMap = {}
        self.task_arg_map = {}
            
        
    ######################################################## MISSION ############################################################ 
    def start_mission(self):
        # dynamic import the fsm
        logger.info(f"MissionController: start the mission")
        from user.project.Mission import Mission
        Mission.define_mission(self.transitMap, self.task_arg_map)
        
        # start the tm
        logger.info(f"MissionController: start the task manager")
        self.tm = TaskManager(self.drone, None, self.transitMap, self.task_arg_map)
        self.tm_coroutine = asyncio.create_task(self.tm.run())
        
    
    def end_mission(self):
        if self.tm and not self.tm_coroutine.cancelled():
            self.tm_coroutine.cancel()
            self.tm = None
            self.tm_coroutine = None
            
        
    ######################################################## MAIN LOOP ############################################################             
    async def run(self):
        self.drone = DroneStub()
        asyncio.create_task(self.drone.run())
        
        # self.compute = ComputeStub()
        
        while True:
            try:
                # Receive a message
                message = self.socket.recv(flags=zmq.NOBLOCK)
                
                # Log the raw received message
                print(f"Received raw message: {message}")
                
                # Parse the message
                mission_command = cnc_pb2.Mission()
                mission_command.ParseFromString(message)
                print(f"Parsed Command: {mission_command}")
                
                if mission_command.startMission:
                    self.start_mission()
                    response = "Mission starting"
                elif mission_command.stopMission:
                    self.end_mission()
                    response = "Mission stopping"
                else:
                    response = "Unknown command"

                # Send a reply back to the client
                self.socket.send_string(response)
                
            except zmq.Again:
                pass
                
            except Exception as e:
                print(f"Failed to parse message: {e}")
                self.socket.send_string("Error processing command")
            
            await asyncio.sleep(0)
            
            
            

if __name__ == "__main__":
    mc = MissionController()
    asyncio.run(mc.run())