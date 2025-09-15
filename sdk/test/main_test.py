from pathlib import Path
from lark import Lark
from steeleagle_sdk.dsl import build_mission, execute_mission

import asyncio
import os
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sample DSL
dsl_code = None
path = os.path.join(os.path.dirname(__file__), 'test_script.dsl')
with open(path, 'r', encoding='utf-8') as f:
    dsl_code = f.read()

logger.info("DSL Code:\n%s", dsl_code)


async def fsm_runner(fsm):
    await fsm.run()

def main():
    # Build mission
    mission = build_mission(dsl_code)
    logger.info("Start: %s", mission.start_action_id)
    logger.info("Actions: %s", sorted(mission.actions.keys()))
    logger.info("Events: %s", sorted(mission.events.keys()))
    logger.info("Data: %s", sorted(mission.data.keys()))
    logger.info("Transitions:")
    for (state, ev), nxt in sorted(mission.transitions.items()):
        logger.info("  %s + %s -> %s", state, ev, nxt)

    # test runtime
    logger.info("Running...")
    asyncio.run(execute_mission(mission))
if __name__ == "__main__":
    main()
