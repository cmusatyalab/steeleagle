import  asyncio
import logging
import sys
from MissionController import MissionController

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

logger.info("Starting the usr space")
user_path = 'user/project'
logger.info("user_path: %s", user_path)

mc = MissionController(user_path)
asyncio.run(mc.run())
