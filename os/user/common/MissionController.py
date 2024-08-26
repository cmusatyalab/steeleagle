
import os
import sys
import zmq
import asyncio
import logging
from system_call_stubs.DroneStub import DroneStub
from system_call_stubs.ComputeStub import ComputeStub
from common.TaskManager import TaskManager
from cnc_protocol import cnc_pb2


logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class MissionController():
    def __init__(self):
        context = zmq.Context()
        self.socket = context.socket(zmq.REP)
        self.socket.connect('tcp://' + os.environ.get('STEELEAGLE_KERNEL_COMMAND_ADDR')) 
        self.isTerminated = False
        self.tm = None
        self.transitMap = {}
        self.task_arg_map = {}
            
        
    ######################################################## MISSION ############################################################ 
    def start_mission(self):
        # check if the mission is already running
        if self.tm:
            logger.info(f"mission already running")
            return
        
        # dynamic import the fsm
        logger.info(f"start the mission")
        from project.implementation.Mission import Mission
        Mission.define_mission(self.transitMap, self.task_arg_map)
        
        # start the tm
        logger.info(f"start the task manager")
        self.tm = TaskManager(self.drone, None, self.transitMap, self.task_arg_map)
        self.tm_coroutine = asyncio.create_task(self.tm.run())
        
    
    async def end_mission(self):
        if self.tm and not self.tm_coroutine.cancelled():
            self.tm_coroutine.cancel()
            try:
                await self.tm_coroutine 
            except asyncio.CancelledError:
                logger.info("Mission coroutine was cancelled successfully.")
            except Exception as e:
                logger.error(f"An error occurred while ending the mission: {e}")
            finally:
                self.tm = None
                self.tm_coroutine = None
                logger.info("Mission has been ended and cleaned up.")
        else:
            logger.info("Mission not running or already cancelled.")
    ######################################################## MAIN LOOP ############################################################             
    async def run(self):
        self.drone = DroneStub()
        asyncio.create_task(self.drone.run())
        
        # self.compute = ComputeStub()
        while True:
            logger.debug("MC")
            try:
                # Receive a message
                message = self.socket.recv(flags=zmq.NOBLOCK)
                
                # Log the raw received message
                logger.info(f"Received raw message: {message}")
                
                # Parse the message
                mission_command = cnc_pb2.Mission()
                mission_command.ParseFromString(message)
                logger.info(f"Parsed Command: {mission_command}")
                
                if mission_command.startMission:
                    self.start_mission()
                    response = "Mission started"
                elif mission_command.stopMission:
                    await self.end_mission()
                    response = "Mission stopped"
                else:
                    response = "Unknown command"

                # Send a reply back to the client
                self.socket.send_string(response)
                
            except zmq.Again:
                pass
                
            except Exception as e:
                logger.info(f"Failed to parse message: {e}")
                self.socket.send_string("Error processing command")
            
            await asyncio.sleep(0)
            
            
            

if __name__ == "__main__":
    mc = MissionController()
    asyncio.run(mc.run())