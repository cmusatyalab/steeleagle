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
    """Compile DSL source text into a MissionIR object.
    
    Args:
        dsl_code (str): string representation of a DSL file

    Returns:
        MissionIR: a mission intermediate representation
    """
    tree = _parser.parse(dsl_code) 
    mission = DroneDSLTransformer().transform(tree)
    logger.info(
        "Compiled DSL: start=%s, actions=%d, events=%d",
        mission.start_action_id, len(mission.actions), len(mission.events),
    )
    return mission

def cli_compile_dsl():
    """Command line utility for compiling DSL scripts.

    Command line script that takes a DSL file as input and writes the compiled mission file
    to the specified output path.

    Args:
        dsl_file (str): input DSL file path (positional argument 0, required)
        output (str): output mission JSON path (`--output` or `-o`, default: `./mission.json`)
    """
    import argparse
    from dataclasses import asdict
    import json
    parser = argparse.ArgumentParser(description="SteelEagle DSL compiler.")
    parser.add_argument("dsl_file", help="Path to DSL file")
    parser.add_argument("-o", "--output", type=str, default="mission.json", help="Name of the output file (type: JSON)")
    args = parser.parse_args()

    mission_json_text = ''
    with open(args.dsl_file, 'r') as file:
        dsl_content = file.read()
        mission = build_mission(dsl_content)
        mission_json_text = json.dumps(asdict(mission))
        print("Mission compiled!")

    with open(args.output, 'w') as file:
        file.write(mission_json_text)
        print(f"Wrote contents to {args.output}.")

__all__ = ["build_mission", "compile"]
