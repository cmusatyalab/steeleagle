import json
from typing import Optional, List
from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.duration_pb2 import Duration
from google.protobuf.json_format import ParseDict
from enum import Enum

from .mission_store import MissionStore
from ..protocol.services import compute_service_pb2, compute_service_pb2_grpc
import grpc
from ..protocol.common_pb2 import common
from .helper import run_unary

class Compute:
    def __init__(self, channel, mission_store: MissionStore):
        self.channel = grpc.aio.insecure_channel(channel)
        self.compute = compute_service_pb2_grpc.ComputeStub(self.channel)
        self.mission_store = mission_store

    async def get_result(self, topic):
        source = "results"
        return await self.mission_store.get_latest(source, topic)

    async def add_datasinks(self, **kwargs) -> common.Response:
        """Add datasinks to consumer list.

        Takes a list of datasinks and adds them to the current consumer list.

        Attributes:
            datasinks (List[params.DatasinkInfo]): name of target datasinks
        """
        
        req = compute_service_pb2.AddDatasinksRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_unary(self.compute.AddDatasinks, req)
    
    async def set_datasinks(self, **kwargs) -> common.Response:
        """Set the datasink consumer list.

        Takes a list of datasinks and replaces the current consumer list with them.

        Attributes:
            datasinks (List[params.DatasinkInfo]): name of target datasinks
        """
        
        req = compute_service_pb2.SetDatasinksRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_unary(self.compute.SetDatasinks, req)

    async def remove_datasinks(self, **kwargs) -> common.Response:
        """Remove datasinks from consumer list.

        Takes a list of datasinks and removes them from the current consumer list.

        Attributes:
            datasinks (List[params.DatasinkInfo]): name of target datasinks
        """
        
        req = compute_service_pb2.RemoveDatasinksRequest()
        ParseDict(json.dumps(kwargs), req)
        return await run_unary(self.compute.RemoveDatasinks, req)
