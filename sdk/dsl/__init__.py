from __future__ import annotations
import logging
from pathlib import Path
import asyncio
from typing import Union

from lark import Lark
from .compiler.ir import MissionIR
from .compiler.transformer import DroneDSLTransformer
from .runtime.fsm import MissionFSM

logger = logging.getLogger(__name__)

# --- Grammar and parser ---
_GRAMMAR_PATH = Path(__file__).resolve().parent / "grammar" / "dronedsl.lark"
_grammar = _GRAMMAR_PATH.read_text(encoding="utf-8")
_parser = Lark(_grammar, parser="lalr", start="start")


# --- Public API ---

def build_mission(dsl_code: str):
    """
    Compile DSL source text into a MissionIR object.

    Args:
        dsl_code: DSL code as a string.

    Returns:
        MissionIR object representing the compiled mission.
    """
    tree = _parser.parse(dsl_code)
    mission = DroneDSLTransformer().transform(tree)

    logger.info(
        "Compiled DSL: start=%s, actions=%d, events=%d",
        mission.start_action_id, len(mission.actions), len(mission.events)
    )
    return mission



async def execute_mission(msn: MissionIR):
    """
    Compile and run DSL code (from string or file).
    """
    fsm = MissionFSM(msn)
    await fsm.run()


__all__ = ["build_mission", "execute_mission"]