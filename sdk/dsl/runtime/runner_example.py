import asyncio
from runtime.fsm import MissionFSM
from compiler.transformer import DroneDSLTransformer
from lark import Lark
from pathlib import Path
GRAMMAR_PATH = Path("../grammar/dronedsl.lark")
grammar = GRAMMAR_PATH.read_text(encoding="utf-8")
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

async def main():
    parser = Lark(grammar, parser="lalr", start="start")
    tree = parser.parse(dsl_code)
    mission = DroneDSLTransformer().transform(tree)
    fsm = MissionFSM(mission)
    await fsm.run()  

if __name__ == "__main__":
    asyncio.run(main())
