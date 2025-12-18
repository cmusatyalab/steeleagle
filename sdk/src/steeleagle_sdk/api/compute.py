import logging
from typing import List

import grpc
from google.protobuf.json_format import ParseDict

from ..protocol.services import compute_service_pb2 as compute_proto
from ..protocol.services.compute_service_pb2_grpc import ComputeStub
from .datatypes.common import Response
from .datatypes.compute import DatasinkInfo
from .mission_store import MissionStore
from .utils import run_unary

logger = logging.getLogger(__name__)


class Compute:
    def __init__(self, channel: grpc.aio.Channel, mission_store: MissionStore):
        self.compute = ComputeStub(channel)
        self.mission_store = mission_store

    async def get_result(self, topic):
        source = "results"
        return await self.mission_store.get_latest(source, topic)

    async def add_datasinks(self, datasinks: List[DatasinkInfo]) -> Response:
        req = compute_proto.AddDatasinksRequest()
        for d in datasinks:
            ParseDict(d.model_dump(exclude_none=True), req.datasinks.add())
        return await run_unary(self.compute.AddDatasinks, req)

    async def set_datasinks(self, datasinks: List[DatasinkInfo]) -> Response:
        """Set the datasink consumer list.

        Takes a list of datasinks and replaces the current consumer list with them.

        Attributes:
            datasinks (List[params.DatasinkInfo]): name of target datasinks
        """

        req = compute_proto.SetDatasinksRequest()
        for d in datasinks:
            ParseDict(d.model_dump(exclude_none=True), req.datasinks.add())
        return await run_unary(self.compute.SetDatasinks, req)

    async def remove_datasinks(self, datasinks: List[DatasinkInfo]) -> Response:
        """Remove datasinks from consumer list.

        Takes a list of datasinks and removes them from the current consumer list.

        Attributes:
            datasinks (List[params.DatasinkInfo]): name of target datasinks
        """

        req = compute_proto.RemoveDatasinksRequest()
        for d in datasinks:
            ParseDict(d.model_dump(exclude_none=True), req.datasinks.add())
        return await run_unary(self.compute.RemoveDatasinks, req)
