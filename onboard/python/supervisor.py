# SPDX-FileCopyrightText: 2023 Carnegie Mellon University - Satyalab
#
# SPDX-License-Identifier: GPL-2.0-only

import argparse
import asyncio
import importlib
import logging
import os
import subprocess
import sys
import time
from zipfile import ZipFile

#from websocket_client import WebsocketClient
import nest_asyncio
import requests
import validators
import zmq
from cnc_protocol import cnc_pb2
from gabriel_client.websocket_client import ProducerWrapper, WebsocketClient
from gabriel_protocol import gabriel_pb2
from syncer import sync

nest_asyncio.apply()

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
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
        self.drone_id = None
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
            kwargs = {}
            if args.sim:
                kwargs['sim'] = True
            if args.lowdelay:
                kwargs['lowdelay'] = True
            if args.dronename:
                kwargs['dronename'] = args.dronename
            if args.droneip:
                kwargs['droneip'] = args.droneip
            logger.info(f"{kwargs=}")
            self.drone = getattr(Drone, args.drone)(**kwargs)
        except Exception as e:
            logger.info('Could not initialize {args.drone}, name does not exist. Aborting.')
            sys.exit(0)

        # Set the Gabriel soure
        self.source = 'telemetry'
        self.reload = False
        self.mission = None
        self.missionTask = None
        self.manual = True # Default to manual control
        self.heartbeats = 0
        self.zmq = zmq.Context().socket(zmq.REQ)
        self.zmq.connect(f'tcp://{args.server}:{args.zmqport}')
        self.tlogfile = None
        if args.trajectory:
            self.tlogfile = open("trajectory.log", "w")

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
        logger.debug('Start mission supervisor')
        logger.debug(self)
        # Stop existing mission (if there is one)
        self.stop_mission()
        # Start new task
        logger.debug('MS import')
        module_prefix = self.drone_id
        if not self.reload:
            logger.info('first time...')
            importlib.import_module(f"{module_prefix}.mission")
            importlib.import_module(f"{module_prefix}.task_defs")
            importlib.import_module(f"{module_prefix}.transition_defs")
        else:
            logger.info('Reloading...')
            modules = sys.modules.copy()
            for module in modules.values():
                if module.__name__.startswith(f'{module_prefix}.mission') or module.__name__.startswith(f'{module_prefix}.task_defs') or module.__name__.startswith('{module_prefix}.transition_defs'):
                    importlib.reload(module)
        logger.debug('MC init')
        #from mission.MissionController import MissionController
        Mission = importlib.import_module(f"{module_prefix}.mission.MissionController")
        self.mission = getattr(Mission, "MissionController")(self.drone, self.cloudlet)
        logger.debug('Running flight script!')
        self.missionTask = asyncio.create_task(self.mission.run())
        self.reload = True

    def stop_mission(self):
        if self.mission and not self.missionTask.cancelled():
            logger.info('Mission script stop signalled')
            self.missionTask.cancel()
            self.mission = None
            self.missionTask = None

    def download(self, url: str):
        #download zipfile and extract reqs/flight script from cloudlet
        try:
            filename = url.rsplit(sep='/')[-1]
            logger.info(f'Writing {filename} to disk...')
            r = requests.get(url, stream=True)
            with open(filename, mode='wb') as f:
                for chunk in r.iter_content():
                    f.write(chunk)
            os.makedirs(self.drone_id, exist_ok=True)
            z = ZipFile(filename)
            sys.path.append(self.drone_id)
            os.chdir(self.drone_id)
            try:
                subprocess.check_call(['rm', '-rf', './task_defs', './mission', './transition_defs'])
            except subprocess.CalledProcessError as e:
                logger.debug(f"Error removing old task/transition defs: {e}")
            z.extractall()
            self.install_prereqs()
            os.chdir('..')
        except Exception as e:
            print(e)

    def install_prereqs(self) -> bool:
        ret = False
        # Pip install prerequsites for flight script
        try:
            subprocess.check_call(['python3', '-m', 'pip', 'install', '-r', './requirements.txt'])
            ret = True
        except subprocess.CalledProcessError as e:
            logger.debug(f"Error pip installing requirements.txt: {e}")
        return ret


    async def commandHandler(self):
        name = await self.drone.getName()

        req = cnc_pb2.Extras()
        req.drone_id = name
        self.drone_id = name
        while True:
            await asyncio.sleep(0)
            try:
                self.zmq.send(req.SerializeToString())
                rep = self.zmq.recv()
                if b'No commands.' != rep:
                    extras  = cnc_pb2.Extras()
                    extras.ParseFromString(rep)
                    if extras.cmd.rth:
                        logger.info('RTH signaled from commander')
                        self.stop_mission()
                        self.manual = False
                        asyncio.create_task(self.drone.rth())
                    elif extras.cmd.halt:
                        logger.info('Killswitch signaled from commander')
                        self.stop_mission()
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
                            logger.info('Received manual takeoff')
                            asyncio.create_task(self.drone.takeOff())
                        elif extras.cmd.land:
                            logger.info('Received manual land')
                            asyncio.create_task(self.drone.land())
                        else:
                            logger.info('Received manual PCMD')
                            pitch = extras.cmd.pcmd.pitch
                            yaw = extras.cmd.pcmd.yaw
                            roll = extras.cmd.pcmd.roll
                            gaz = extras.cmd.pcmd.gaz
                            gimbal_pitch = extras.cmd.pcmd.gimbal_pitch
                            logger.debug(f'Got PCMD values: {pitch} {yaw} {roll} {gaz} {gimbal_pitch}')
                            asyncio.create_task(self.drone.PCMD(roll, pitch, yaw, gaz))
                            current = await self.drone.getGimbalPitch()
                            asyncio.create_task(self.drone.setGimbalPose(0, current+gimbal_pitch , 0))
                if self.tlogfile: # Log trajectory IMU data
                    speeds = await self.drone.getSpeedRel()
                    fspeed = speeds["speedX"]
                    hspeed = speeds["speedY"]
                    self.tlogfile.write(f"{time.time()},{fspeed},{hspeed} ")
            except Exception as e:
                logger.debug(e)


    '''
    Process results from engines.
    Forward openscout engine results to Cloudlet object
    Parse and deal with results from command engine
    '''
    def processResults(self, result_wrapper):
        if self.cloudlet and result_wrapper.result_producer_name.value != 'telemetry':
            #forward result to cloudlet
            self.cloudlet.processResults(result_wrapper)
            return
        else:
            #process result from command engine
            pass

    def get_producer_wrappers(self):
        async def producer():
            await asyncio.sleep(0)
            self.heartbeats += 1
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
            input_frame.payloads.append('heartbeart'.encode('utf8'))

            extras = cnc_pb2.Extras()
            try:
                extras.drone_id = sync(self.drone.getName())
                extras.location.latitude = sync(self.drone.getLat())
                extras.location.longitude = sync(self.drone.getLng())
                extras.location.altitude = sync(self.drone.getRelAlt())
                logger.debug(f'Latitude: {extras.location.latitude} Longitude: {extras.location.longitude} Altitude: {extras.location.altitude}')
                extras.status.battery = sync(self.drone.getBatteryPercentage())
                extras.status.rssi = sync(self.drone.getRSSI())
                extras.status.mag = sync(self.drone.getMagnetometerReading())
                extras.status.bearing = sync(self.drone.getHeading())
                logger.debug(f'Battery: {extras.status.battery} RSSI: {extras.status.rssi}  Magnetometer: {extras.status.mag} Heading: {extras.status.bearing}')
            except Exception as e:
                logger.debug(f'Error getting telemetry: {e}')

            # Register on the first frame
            if self.heartbeats == 1:
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
                        help='Specify address of Steel Eagle CNC server [default: gabriel-server]')
    parser.add_argument('-p', '--port', default='9099',
                        help='Specify websocket port [default: 9099]')
    parser.add_argument('-l', '--loglevel', default='INFO',
                        help='Set the log level')
    parser.add_argument('-S', '--sim', action='store_true',
        help='Connect to  simulated drone instead of a real drone [default: False]')
    parser.add_argument('-L', '--lowdelay', action='store_true',
        help='Use low delay settings for video streaming [default: False]')
    parser.add_argument('-zp', '--zmqport', type=int, default=6000,
                        help='Specify websocket port [default: 6000]')
    parser.add_argument('-t', '--trajectory', action='store_true',
        help='Log the trajectory of the drone over the flight duration [default: False]')
    parser.add_argument('-i', '--droneip', default='192.168.42.1',
                                    help='Specify drone IP address [default: 192.168.42.1]')

    parser.add_argument('-n', '--dronename',
                                    help='Specify drone name.')
    args = parser.parse_args()
    logging.basicConfig(format="%(levelname)s: %(message)s",
                        level=args.loglevel)
    logger.info(f"{args=}")

    adapter = Supervisor(args)
    await adapter.initializeConnection()
    asyncio.create_task(adapter.commandHandler())

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
