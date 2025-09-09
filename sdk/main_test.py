from pathlib import Path
from lark import Lark
from dsl.compiler.transformer import DroneDSLTransformer
import os
# Load grammar
GRAMMAR_PATH = Path("./dsl/grammar/dronedsl.lark")
grammar = GRAMMAR_PATH.read_text(encoding="utf-8")
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Create parser
parser = Lark(grammar, parser="lalr", start="start")

# Sample DSL

dsl_code = None
with open(os.path.join(os.path.dirname(__file__), 'test_script.dsl'), 'r', encoding='utf-8') as f:
    dsl_code = f.read()

logger.info("DSL Code:\n%s", dsl_code)
def main():
    # Parse
    tree = parser.parse(dsl_code)
    logger.info("Parse tree: %s", tree.pretty())
    # Transform
    mission = DroneDSLTransformer().transform(tree)

    # Print results
    logger.info("Start: %s", mission.start_action_id)
    logger.info("Actions: %s", sorted(mission.actions.keys()))
    logger.info("Events: %s", sorted(mission.events.keys()))
    logger.info("Data: %s", sorted(mission.data.keys()))
    logger.info("Transitions:")
    for (state, ev), nxt in sorted(mission.transitions.items()):
        logger.info("  %s + %s -> %s", state, ev, nxt)

if __name__ == "__main__":
    main()
