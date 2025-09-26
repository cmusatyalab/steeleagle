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
    build_mission(dsl_code)

if __name__ == "__main__":
    main()
