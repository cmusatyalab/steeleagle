import  asyncio
import logging
import os
from util.utils import setup_logging
from MissionController import MissionController

logger = logging.getLogger()
setup_logging(logger, 'mission.logging')


logger.info("Starting the usr space")
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
project_dir = os.path.join(parent_dir, 'project')
logger.info("proj_path: %s", project_dir)

mc = MissionController(project_dir)
asyncio.run(mc.run())
print("Mission controller is done")
