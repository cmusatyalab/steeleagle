import json
import grpc
from typing import Optional, List
from google.protobuf.timestamp_pb2 import Timestamp
from google.protobuf.duration_pb2 import Duration
from google.protobuf.json_format import ParseDict
from enum import Enum

from .mission_store import MissionStore
from ..protocol.services.compute_service_pb2_grpc import ComputeStub
from ..protocol.services.compute_service_pb2 import AddDatasinksRequest, SetDatasinksRequest, RemoveDatasinksRequest, DatasinkInfo

from ..protocol.common_pb2 import Response
from .helper import run_unary

class Compute:
    def __init__(self, channel, mission_store: MissionStore):
        self.channel = grpc.aio.insecure_channel(channel)
        self.compute = ComputeStub(self.channel)
        self.mission_store = mission_store

    async def get_result(self, topic):
        source = "results"
        return await self.mission_store.get_latest(source, topic)

    async def add_datasinks(self, datasinks:List[DatasinkInfo]) -> Response:
        req = AddDatasinksRequest()
        req.datasinks.extend(datasinks)
        return await run_unary(self.compute.AddDatasinks, req)
    
    async def set_datasinks(self, datasinks:List[DatasinkInfo]) -> Response:
        """Set the datasink consumer list.

        Takes a list of datasinks and replaces the current consumer list with them.

        Attributes:
            datasinks (List[params.DatasinkInfo]): name of target datasinks
        """
        
        req = SetDatasinksRequest()
        req.datasinks.extend(datasinks)
        return await run_unary(self.compute.SetDatasinks, req)

    async def remove_datasinks(self, datasinks:List[DatasinkInfo]) -> Response:
        """Remove datasinks from consumer list.

        Takes a list of datasinks and removes them from the current consumer list.

        Attributes:
            datasinks (List[params.DatasinkInfo]): name of target datasinks
        """
        
        req = RemoveDatasinksRequest()
        req.datasinks.extend(datasinks)
        return await run_unary(self.compute.RemoveDatasinks, req)
