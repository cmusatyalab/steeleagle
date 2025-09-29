from __future__ import annotations
import logging
from pathlib import Path

from lark import Lark
from .compiler.ir import MissionIR
from .compiler.transformer import DroneDSLTransformer
logger = logging.getLogger(__name__)

# Load and prepare the DSL parser
_GRAMMAR_PATH = Path(__file__).resolve().parent / "grammar" / "dronedsl.lark"
_grammar = _GRAMMAR_PATH.read_text(encoding="utf-8")
_parser = Lark(_grammar, parser="lalr", start="start")

def build_mission(dsl_code: str) -> MissionIR:
    '''Compile DSL source text into a MissionIR object.'''
    tree = _parser.parse(dsl_code) 
    mission = DroneDSLTransformer().transform(tree)
    logger.info(
        "Compiled DSL: start=%s, actions=%d, events=%d",
        mission.start_action_id, len(mission.actions), len(mission.events),
    )
    return mission


__all__ = ["build_mission"]

