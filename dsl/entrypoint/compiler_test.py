from pathlib import Path
from lark import Lark
from compiler.transformer import DroneDSLTransformer

# Load grammar
GRAMMAR_PATH = Path("../grammar/dronedsl.lark")
grammar = GRAMMAR_PATH.read_text(encoding="utf-8")

# Create parser
parser = Lark(grammar, parser="lalr", start="start")

# Sample DSL

dsl_code_naive = """
Actions:
  TakeOff takeoff1
  Land   land1
  SetRelativePositionENU set (north: 10, east: 20, up: 5, angle: 90)
  Test test1 (param: value)

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
  
  During tack:
    no_longer_red -> detect_patrol
    
"""

def main():
    # Parse
    tree = parser.parse(dsl_code)
    print(tree.pretty())
    # Transform
    mission = DroneDSLTransformer(implicit_done=True).transform(tree)

    # Print results
    print("Start:", mission.start_action_id)
    print("Actions:", sorted(mission.actions.keys()))
    print("Events:", sorted(mission.events.keys()))
    print("Transitions:")
    for (state, ev), nxt in sorted(mission.transitions.items()):
        print(f"  {state} + {ev} -> {nxt}")

if __name__ == "__main__":
    main()