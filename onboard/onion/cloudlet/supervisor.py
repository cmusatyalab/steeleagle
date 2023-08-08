import argparse
import asyncio
import logging
import requests
import subprocess
import sys
import threading
import validators
from zipfile import ZipFile
from implementation.drones import ParrotAnafi
from implementation.cloudlets import ElijahCloudlet

from cnc_protocol import cnc_pb2
from gabriel_protocol import gabriel_pb2
from gabriel_client.websocket_client import ProducerWrapper, WebsocketClient


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class Supervisor:
    def __init__(self):
        self.cloudlet = ElijahCloudlet.ElijahCloudlet()
        kwargs = {'ip': '10.202.0.1'}
        self.drone = ParrotAnafi.ParrotAnafi(**kwargs)
        #connect to drone, if not already
        if not self.drone.isConnected():
            self.drone.connect()
            self.drone.startStreaming(480)
            self.cloudlet.startStreaming(self.drone, 'coco', 30)
        self.source = 'command'
        self.MS = None #mission script
        self.manual = True #default to manual control
        self.heartbeats = 0

    def retrieveFlightScript(self, url: str) -> bool:
        logger.d('String flight plan download')
        self.download(url)

    def executeFlightScript(self):
        self.drone.hover()
        logger.d('Executing flight plan!')
        #start new thread with self.MS
        from script.MS import MS
        self.MS = MS(self.drone, self.cloudlet)
        self.MS.start()

    def download(self, url: str, ):
        #download zipfile and extract reqs/flight script from cloudlet
        r = requests.get(url)
        with open('./script.zip', mode='w', encoding='utf-8') as f:
            f.write(r.content)
        z = ZipFile('./script.zip')
        z.extractall()
        self.install_prereqs()

    def install_prereqs(self) -> bool:
        ret = False
        #pip install prerequsites for flight script
        try:
            subprocess.check_call(['python3', '-m', 'pip', 'install', '-r', './script/requirements.txt'])
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
            #forward result to cloudlet
            self.cloudlet.processResults(result_wrapper)
            return
        else:
            #process result from command engine

            if len(result_wrapper.results) != 1:
                logger.error('Got %d results from server'.
                        len(result_wrapper.results))
                return
                    
            extras = cnc_pb2.Extras()
            result_wrapper.extras.Unpack(extras)

            for result in result_wrapper.results:
                if result.payload_type == gabriel_pb2.PayloadType.TEXT:
                    payload = result.payload.decode('utf-8')
                    if extras.cmd.rth:
                        logger.info('RTH signaled from commander')
                        if self.MS:
                            self.MS._kill()
                        self.drone.disonnect()
                    elif extras.cmd.halt:
                        logger.info('Killswitch signaled from commander')
                        if self.MS:
                            self.MS._kill()
                        self.manual = True
                    elif extras.cmd.script_url:
                        #validate url
                        if validators.url(extras.cmd.script_url):
                            logger.info(f'Flight script sent by commander: {extras.cmd.script_url}')
                            if self.retrieveFlightScript():
                                self.manual = False
                                self.executeFlightScript()
                        else:
                            logger.info(f'Invalid script URL sent by commander: {extras.cmd.script_url}')
                    elif self.manual:
                        if extras.cmd.takeoff:
                            logger.info(f'Received manual takeoff')
                            self.drone.takeOff()
                        elif extras.cmd.land:
                            logger.info(f'Received manual land')
                            self.drone.land()
                        else:
                            logger.info(f'Received manual PCMD')
                            pitch = extras.cmd.pcmd.pitch
                            yaw = extras.cmd.pcmd.yaw
                            roll = extras.cmd.pcmd.roll
                            gaz = extras.cmd.pcmd.gaz
                            logger.debug(f'Got PCMD values: {pitch} {yaw} {roll} {gaz}')

                            self.drone.PCMD(roll, pitch, yaw, gaz)
                else:
                    logger.error(f"Got result type {result.payload_type}. Expected TEXT.")

    def get_producer_wrappers(self):
        async def producer():
            await asyncio.sleep(1)
            if self.heartbeats < 2:
                self.heartbeats += 1
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.TEXT
            input_frame.payloads.append('heartbeart'.encode('utf8'))
    
            extras = cnc_pb2.Extras()
            extras.drone_id = self.drone.getName()
            extras.location.latitude = self.drone.getLat()
            extras.location.longitude = self.drone.getLng()
            extras.location.altitude = self.drone.getRelAlt()
            try:
                extras.status.battery = self.drone.getBatteryPercentage()
                extras.status.rssi = self.drone.getRSSI()
                extras.status.mag = self.drone.getMagnetometerReading()
                extras.status.bearing = self.drone.getHeading()
                logger.debug(f'Battery: {extras.status.battery} RSSI: {extras.status.rssi}  Magnetometer: {extras.status.mag} Heading: {extras.status.bearing}')
            except Exception as e:
                logger.error(f'Error getting telemetry: {e}')
            if self.heartbeats < 2:
                extras.registering = True
            input_frame.extras.Pack(extras)
            return input_frame
    
        return ProducerWrapper(producer=producer, source_name=self.source)

def _main():
    parser = argparse.ArgumentParser(prog='supervisor',
        description='Manage drones via olympe.')
    parser.add_argument('-s', '--server', default='gabriel-server',
                        help='Specify address of Steel Eagle CNC server [default: gabriel-server')
    parser.add_argument('-p', '--port', default='9099',
                        help='Specify websocket port [default: 9099]')
    parser.add_argument('-l', '--loglevel', default='INFO',
                        help='Set the log level')

    args = parser.parse_args()
    logging.basicConfig(format="%(levelname)s: %(message)s",
                        level=args.loglevel)
    adapter = Supervisor()

    gabriel_client = WebsocketClient(
        args.server, args.port,
        [adapter.get_producer_wrappers(), adapter.cloudlet.sendFrame()],  adapter.processResults
    )
    gabriel_client.launch()

if __name__ == "__main__":
    _main()
