import asyncio
import logging
import time

from ModalAISeekerDrone import ModalAISeekerDrone

logger = logging.getLogger(__name__)
logging.basicConfig()
logger.setLevel(logging.INFO)

async def main():
    logger.info("Starting script")
    # args = {'server_address': '162.172.22.130'}
    args = {'server_address': '192.168.8.1'}

    drone = ModalAISeekerDrone(**args)
    await drone.connect()

    #connected = await drone.isConnected()
    #print(f"Connected: {connected}")

    #satellites = await drone.getBatteryPercentage()
    #print(satellites)

    await drone.takeOff()

    #logger.info("Done taking off")

    await drone.startOffboardMode()

    logger.info("Switched to offboard flight mode")

    time.sleep(5)

    print(await drone.getLat())
    print(await drone.getLng())
    await drone.moveBy(0, 0, 10, 0)
    await drone.setVelocity(0, 0, 0, 0)

if __name__ == "__main__":
    asyncio.run(main())
