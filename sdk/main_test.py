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

dsl_code_naive = """
Actions:
  TakeOff takeoff1 (take_off_altitude: 10.0)
  Land   land1

Mission:
  Start takeoff1
"""

dsl_code = """
Actions:
  
  PrePatrolSequence prepatrol (altitude: 15.0, gimbal_pitch: 0.0)
  
  ConfigureCompute compute_config (model: coco, hsv_lower: [0, 70, 50], hsv_upper: [10, 255, 255])
  
  DetectPatrol detect_patrol (area: sectorA, hover_time: 2.0, alt: 15.0, prepatrol: prepatrol, compute_config: compute_config)
  
  Track track (target: person, lost_timeout: 30.0)
  

Events:
  HSVReached red_color (compute_type: openscout)
  
  DetectionFound person_detected (compute_type: openscout, target: person)
  
  Allof red_jacket_person_detected (events: [red_color, person_detected])

  Not no_longer_red (event: red_color)

Mission:
  Start detect_patrol

  During detect_patrol:
    red_jacket_person_detected -> track
  
  During track:
    no_longer_red -> detect_patrol
    
"""

def main():
    # Parse
    tree = parser.parse(dsl_code_naive)
    logger.info("Parse tree: %s", tree.pretty())
    # Transform
    mission = DroneDSLTransformer().transform(tree)

    # Print results
    logger.info("Start: %s", mission.start_action_id)
    logger.info("Actions: %s", sorted(mission.actions.keys()))
    logger.info("Events: %s", sorted(mission.events.keys()))
    logger.info("Transitions:")
    for (state, ev), nxt in sorted(mission.transitions.items()):
        logger.info("  %s + %s -> %s", state, ev, nxt)

if __name__ == "__main__":
    main()
