import asyncio
import logging
import os
import sys

from MissionController import MissionController

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

logger.info("Starting the usr space")
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
project_dir = os.path.join(parent_dir, "project")
logger.info("proj_path: %s", project_dir)

mc = MissionController(project_dir)
asyncio.run(mc.run())
