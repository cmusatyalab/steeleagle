from typing import Any
from ...api.vehicle import Vehicle
from ...api.compute import Compute
import grpc
from ...api.mission_store import MissionStore
from .fsm import MissionFSM
from ..compiler.ir import MissionIR
import logging
logger = logging.getLogger(__name__)

VEHICLE: Vehicle = None
COMPUTE: Compute = None
MAP: Any = None
    

def init(mission: MissionIR, vehicle_address: str, telemetry_address: str, result_address: str, map: Any) -> None:
    channel = grpc.aio.insecure_channel(vehicle_address)
    mission_store = MissionStore(telemetry_address, result_address)
    mission_store.start()
    vehicle = Vehicle(channel, mission_store)
    compute = Compute(channel, mission_store)
    
    global VEHICLE, COMPUTE, MAP
    VEHICLE = vehicle
    COMPUTE = compute
    MAP = map
    
    fsm = MissionFSM(mission)
    return fsm
