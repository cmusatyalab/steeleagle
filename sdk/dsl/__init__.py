from __future__ import annotations
import logging
from pathlib import Path
import asyncio

from lark import Lark
from typing import Dict, List

from .partitioner.partition import Partition
from .partitioner.geopoints import GeoPoints
from .partitioner.utils import parse_kml_file
from .compiler.ir import MissionIR
from .compiler.transformer import DroneDSLTransformer
from .runtime.fsm import MissionFSM

from ..api.actions.primitives import control as control_mod
from ..api.actions.primitives import compute as compute_mod
from ..api.actions.primitives import report as report_mod

from ..protocol.services import compute_service_pb2_grpc as compute_rpc
from ..protocol.services import control_service_pb2_grpc as control_rpc
from ..protocol.services import report_service_pb2_grpc as report_rpc

ComputeStub = compute_rpc.ComputeStub
ControlStub = control_rpc.ControlStub
ReportStub  = report_rpc.ReportStub

logger = logging.getLogger(__name__)

# --- Grammar and parser ---
_GRAMMAR_PATH = Path(__file__).resolve().parent / "grammar" / "dronedsl.lark"
_grammar = _GRAMMAR_PATH.read_text(encoding="utf-8")
_parser = Lark(_grammar, parser="lalr", start="start")


def build_mission(dsl_code: str) -> MissionIR:
    """
    Compile DSL source text into a MissionIR object.
    """
    try:
        tree = _parser.parse(dsl_code) 
    except Exception as e:
        logger.error("DSL parsing error: %s", e)
        raise
    
    mission = DroneDSLTransformer().transform(tree)
    logger.info(
        "Compiled DSL: start=%s, actions=%d, events=%d",
        mission.start_action_id, len(mission.actions), len(mission.events),
    )
    return mission

def partition_geopoints(
    partition: Partition,
    kml_path: str,
) -> Dict[str, List[GeoPoints]]:

    path = Path(kml_path)
    if not path.exists():
        raise FileNotFoundError(f"KML file not found: {path}")

    raw_map = parse_kml_file(str(path))
    if not raw_map:
        logger.warning("No Placemarks found in KML: %s", path)
        return {}
    
    out: Dict[str, List[GeoPoints]] = {}
    for area, raw in raw_map.items():
        if len(raw) < 3:
            logger.warning("Area %s has < 3 points; skipping.", area)
            continue

        origin_wgs = raw.centroid()
        projected = raw.convert_to_projected()
        poly = projected.to_polygon()

        # partition in projected space
        parts_m = partition.generate_partitioned_geopoints(poly)

        # inverse-project results back to WGS84
        parts_wgs = [GeoPoints(p).inverse_project_from(origin_wgs) for p in parts_m]
        out[area] = parts_wgs

        logger.info(
            "Partitioned '%s': %d segment(s), %d point(s)",
            area,
            len(parts_wgs),
            sum(len(seg) for seg in parts_wgs),
        )

    return out

async def execute_mission(msn: MissionIR, control: ControlStub, compute: ComputeStub, report: ReportStub) -> None:
    control_mod.STUB = control
    compute_mod.STUB = compute
    report_mod.STUB  = report

    fsm = MissionFSM(msn)
    await fsm.run()


__all__ = ["build_mission", "execute_mission"]

