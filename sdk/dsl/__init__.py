from __future__ import annotations
import logging
from pathlib import Path
import asyncio

from lark import Lark
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
    tree = _parser.parse(dsl_code)
    mission = DroneDSLTransformer().transform(tree)
    logger.info(
        "Compiled DSL: start=%s, actions=%d, events=%d",
        mission.start_action_id, len(mission.actions), len(mission.events),
    )
    return mission


async def execute_mission(msn: MissionIR, control: ControlStub, compute: ComputeStub, report: ReportStub) -> None:
    """
    Run a compiled mission with the provided service stubs.
    This wires the stubs into the action modules' globals before running.
    """
    control_mod.STUB = control
    compute_mod.STUB = compute
    report_mod.STUB  = report

    fsm = MissionFSM(msn)
    await fsm.run()


__all__ = ["build_mission", "execute_mission"]

