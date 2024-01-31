# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import argparse
import asyncio
import nest_asyncio
nest_asyncio.apply()
from syncer import sync
import logging
import requests
import subprocess
import sys
import validators
import os
from zipfile import ZipFile
import importlib

from cnc_protocol import cnc_pb2
from gabriel_protocol import gabriel_pb2
from gabriel_client.websocket_client import ProducerWrapper, WebsocketClient
#from websocket_client import WebsocketClient

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
fh = logging.FileHandler('supervisor.log')
formatter = logging.Formatter('%(asctime)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

class Supervisor:

    def __init__(self, args):
        # Import the files corresponding to the selected drone/cloudlet
        drone_import = f"implementation.drones.{args.drone}"
        cloudlet_import = f"implementation.cloudlets.{args.cloudlet}"
        try:
            Drone = importlib.import_module(drone_import)
        except Exception as e:
            logger.info('Could not import drone {args.drone}')
            sys.exit(0)
        try:
            Cloudlet = importlib.import_module(cloudlet_import)
        except Exception as e:
            logger.info('Could not import cloudlet {args.cloudlet}')
            sys.exit(0)

        try:
            self.cloudlet = getattr(Cloudlet, args.cloudlet)()
        except Exception as e:
            logger.info('Could not initialize {args.cloudlet}, name does not exist. Aborting.')
            sys.exit(0)
        try:
            if args.sim:
                kwargs = {'sim': True}
            self.drone = getattr(Drone, args.drone)(**kwargs)
        except Exception as e:
            logger.info('Could not initialize {args.drone}, name does not exist. Aborting.')
            sys.exit(0)

        # Set the Gabriel soure
        self.source = 'command'
        self.mission = None
        self.missionTask = None
        self.manual = True #default to manual control
        self.heartbeats = 0

    async def initializeConnection(self):
        await self.drone.connect()
        await self.drone.startStreaming()
        self.cloudlet.startStreaming(self.drone, 'coco', 30)

    async def executeFlightScript(self, url: str):
        logger.debug('Starting flight plan download...')
        try:
            self.download(url)
        except Exception as e:
            logger.debug('Flight script download failed! Aborting.')
            return
        logger.debug('Flight script downloaded...')
        self.start_mission()

    def start_mission(self):
        # Stop existing mission (if there is one)
        self.stop_mission()
        # Start new task
        from MS import MS
        self.mission = MS(self.drone, self.cloudlet)
        logger.debug('Running flight script!')
        self.missionTask = asyncio.create_task(self.mission.run())

    def stop_mission(self):
        if self.mission:
            asyncio.run(self.mission.stop())
            logger.info('Mission script stop signalled')
            self.mission = None

    def kill_mission(self):
        if self.mission and self.missionTask and not self.missionTask.cancelled():
            logger.info('Mission script kill signalled')
            self.missionTask.cancel() # Hard stops the mission with an exception

    def download(self, url: str):
        # Download zipfile and extract reqs/flight script from cloudlet
        filename = url.rsplit(sep='/')[-1]
        logger.info(f'Writing {filename} to disk...')
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(filename, mode='wb') as f:
            for chunk in r.iter_content():
                f.write(chunk)
        z = ZipFile(filename)
        os.system("rm -rf ./task_defs ./python")
        z.extractall()
        os.system("mv python/* .")
        self.install_prereqs()

    def install_prereqs(self) -> bool:
        ret = False
        # Pip install prerequsites for flight script
        try:
            subprocess.check_call(['python3', '-m', 'pip', 'install', '-r', './requirements.txt'])
            ret = True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error pip installing requirements.txt: {e}")
        return ret

    '''
    Process results from engines.
    Forward openscout engine results to Cloudlet object
    Parse and deal with results from command engine
    '''
    def processResults(self, result_wrapper):
        if self.cloudlet and result_wrapper.result_producer_name.value != 'command':
            # Forward result to cloudlet
            self.cloudlet.processResults(result_wrapper)
            return
        else:
            # Process result from command engine
            if len(result_wrapper.results) != 1:
                return

            extras = cnc_pb2.Extras()
            result_wrapper.extras.Unpack(extras)

            for result in result_wrapper.results:
                if result.payload_type == gabriel_pb2.PayloadType.TEXT:
                    payload = result.payload.decode('utf-8')
                    if extras.cmd.rth:
                        logger.info('RTH signaled from commander')
                        self.kill_mission()
                        self.manual = False
                        asyncio.create_task(self.drone.rth())
                    elif extras.cmd.halt:
                        logger.info('Killswitch signaled from commander')
                        self.kill_mission()
                        self.manual = True
                        logger.info('Manual control is now active!')
                        # Try cancelling the RTH task if it exists
                        sync(self.drone.hover())
                    elif extras.cmd.script_url:
                        # Validate url
                        if validators.url(extras.cmd.script_url):
                            logger.info(f'Flight script sent by commander: {extras.cmd.script_url}')
                            self.manual = False
                            asyncio.create_task(self.executeFlightScript(extras.cmd.script_url))
                        else:
                            logger.info(f'Invalid script URL sent by commander: {extras.cmd.script_url}')
                    elif self.manual:
                        if extras.cmd.takeoff:
                            logger.info(f'Received manual takeoff')
                            asyncio.create_task(self.drone.takeOff())
                        elif extras.cmd.land:
                            logger.info(f'Received manual land')
                            asyncio.create_task(self.drone.land())
                        else:
                            logger.info(f'Received manual PCMD')
                            pitch = extras.cmd.pcmd.pitch
                            yaw = extras.cmd.pcmd.yaw
                            roll = extras.cmd.pcmd.roll
                            gaz = extras.cmd.pcmd.gaz
                            logger.debug(f'Got PCMD values: {pitch} {yaw} {roll} {gaz}')

                            asyncio.create_task(self.drone.PCMD(roll, pitch, yaw, gaz))
                else:
                    logger.error(f"Got result type {result.payload_type}. Expected TEXT.")

    def get_producer_wrappers(self):
        async def producer():
            await asyncio.sleep(0.1)
            self.heartbeats += 1
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
            input_frame.payloads.append('heartbeart'.encode('utf8'))
    
            extras = cnc_pb2.Extras()
            extras.drone_id = sync(self.drone.getName())
            extras.location.latitude = sync(self.drone.getLat())
            extras.location.longitude = sync(self.drone.getLng())
            extras.location.altitude = sync(self.drone.getRelAlt())
            logger.debug(f'Latitude: {extras.location.latitude} Longitude: {extras.location.longitude} Altitude: {extras.location.altitude}')
            try:
                extras.status.battery = sync(self.drone.getBatteryPercentage())
                extras.status.rssi = sync(self.drone.getRSSI())
                extras.status.mag = sync(self.drone.getMagnetometerReading())
                extras.status.bearing = sync(self.drone.getHeading())
                logger.debug(f'Battery: {extras.status.battery} RSSI: {extras.status.rssi}  Magnetometer: {extras.status.mag} Heading: {extras.status.bearing}')
            except Exception as e:
                logger.error(f'Error getting telemetry: {e}')
            if self.heartbeats < 100:
                extras.registering = True
            logger.debug('Producing Gabriel frame!')
            input_frame.extras.Pack(extras)
            return input_frame
    
        return ProducerWrapper(producer=producer, source_name=self.source)


async def _main():
    parser = argparse.ArgumentParser(prog='supervisor',
        description='Bridges python API drones to SteelEagle.')
    parser.add_argument('-d', '--drone', default='ParrotAnafiDrone',
                        help='Set the type of drone to interface with [default: ParrotAnafiDrone]')
    parser.add_argument('-c', '--cloudlet', default='PureOffloadCloudlet',
                        help='Set the type of offload method to the cloudlet [default: PureOffloadCloudlet]')
    parser.add_argument('-s', '--server', default='gabriel-server',
                        help='Specify address of Steel Eagle CNC server [default: gabriel-server')
    parser.add_argument('-p', '--port', default='9099',
                        help='Specify websocket port [default: 9099]')
    parser.add_argument('-l', '--loglevel', default='INFO',
                        help='Set the log level')
    parser.add_argument('-S', '--sim', action='store_true',
                        help='Connect to  simulated drone instead of a real drone [default: False]')

    args = parser.parse_args()
    logging.basicConfig(format="%(levelname)s: %(message)s",
                        level=args.loglevel)

    adapter = Supervisor(args)
    await adapter.initializeConnection()

    logger.debug("Launching Gabriel")
    gabriel_client = WebsocketClient(
        args.server, args.port,
        [adapter.get_producer_wrappers(), adapter.cloudlet.sendFrame()],  adapter.processResults
    )
    try:
        gabriel_client.launch()
    except KeyboardInterrupt:
        adapter.cloudlet.stopStreaming()
        await adapter.drone.stopStreaming()
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(_main())
