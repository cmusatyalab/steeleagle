import asyncio
import zmq
import time
import logging
# Utility import
from util.config import query_config
from util.sockets import setup_zmq_socket, SocketOperation
# Gabriel import
from gabriel_client.zeromq_client import ZeroMQClient
from gabriel_client.gabriel_client import InputProducer
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine
# Protocol import
from steeleagle_sdk.protocol.messages.telemetry_pb2 import DriverTelemetry, Frame, MissionTelemetry
from steeleagle_sdk.protocol.messages.result_pb2 import ComputeResult

logger = logging.getLogger('kernel/handlers/stream_handler')

class StreamHandler:
    '''
    Pushes telemetry and imagery to both local compute and remote compute
    servers and relays results over the result socket.
    '''
    def __init__(self, law_authority):
        # Reference to the law authority
        self.law_authority = law_authority
        # Create the result socket
        self._result_sock = zmq.Context().socket(zmq.PUB)
        setup_zmq_socket(
            self._result_sock,
            'internal.streams.results',
            SocketOperation.BIND
            )
        # Configure local compute handler
        self._local_compute_handler = None
        self._lch_task = None
        try:
            # Create producers
            self._local_producers = [
                self.get_driver_telemetry_producer(),
                self.get_imagery_producer(),
                self.get_mission_telemetry_producer()
            ]
            lc_server = \
                query_config('internal.streams.local_compute').replace('unix', 'ipc')
            self._local_compute_handler = ZeroMQClient(lc_server, self._local_producers, self.process)
        except Exception:
            logger.warning('No valid configuration found for local compute handler, not running it')
            self._local_producers = []
            self._local_compute_handler = None
        # Configure remote compute handler
        self._remote_compute_handler = None
        self._rch_task = None
        try:
            # Create producers
            self._remote_producers = [
                self.get_driver_telemetry_producer(),
                self.get_imagery_producer(),
                self.get_mission_telemetry_producer()
            ]
            rc_server = \
                query_config('cloudlet.remote_compute_service')
            self._remote_compute_handler = ZeroMQClient(f'tcp://{rc_server}', self._remote_producers, self.process)
        except Exception:
            logger.warning('No valid configuration found for remote compute handler, not running it')
            self._remote_producers = []
            self._remote_compute_handler = None

    async def start(self):
        '''
        Start the Gabriel clients. Note: this does not start the producers, those
        must be started separately using `update_target_engines`.
        '''
        if self._local_compute_handler:
            self._lch_task = asyncio.create_task(self._local_compute_handler.launch_async())
        else:
            self._lch_task = asyncio.sleep(0) # Default task so gather does not cause an exception
        if self._remote_compute_handler:
            self._rch_task = asyncio.create_task(self._remote_compute_handler.launch_async())
        else:
            self._rch_task = asyncio.sleep(0)

    def update_target_engines(self, target_engines):
        '''
        Update the target engines for local/remote producers. Decides which server the
        engine is on based on the name prexif (remote:____ for a remote engine and 
        local:____ for a local engine).
        '''
        logger.info(f'Updating target engines to {target_engines}')
        remote_engines = []
        local_engines = []
        for engine in target_engines:
            if 'remote:' in engine:
                remote_engines.append(engine.replace('remote:', ''))
            elif 'local:' in engine:
                local_engines.append(engine.replace('local:', ''))
        for producer in self._remote_producers:
            if producer.is_running:
                producer.stop()
            if len(remote_engines):
                producer.start(remote_engines)
        for producer in self._local_producers:
            if producer.is_running:
                producer.stop()
            if len(local_engines):
                producer.start(local_engines)

    async def wait_for_termination(self):
        await asyncio.gather(self._lch_task, self._rch_task)

    def get_driver_telemetry_producer(self):
        driver_sock = zmq.asyncio.Context().socket(zmq.SUB)
        driver_sock.setsockopt(zmq.SUBSCRIBE, b'')
        setup_zmq_socket(
            driver_sock,
            'internal.streams.driver_telemetry',
            SocketOperation.CONNECT
            )
        return InputProducer(
                self._base_producer(
                    driver_sock,
                    DriverTelemetry(),
                    gabriel_pb2.PayloadType.TEXT
                    ),
                [],
                source_name="driver_telemetry"
                )
    
    def get_imagery_producer(self):
        imagery_sock = zmq.asyncio.Context().socket(zmq.SUB)
        imagery_sock.setsockopt(zmq.SUBSCRIBE, b'')
        setup_zmq_socket(
            imagery_sock,
            'internal.streams.imagery',
            SocketOperation.CONNECT
            )
        return InputProducer(
                self._base_producer(
                    imagery_sock,
                    Frame(),
                    gabriel_pb2.PayloadType.IMAGE
                    ),
                [],
                source_name="images"
                )
    
    def get_mission_telemetry_producer(self):
        mission_sock = zmq.asyncio.Context().socket(zmq.SUB)
        mission_sock.setsockopt(zmq.SUBSCRIBE, b'')
        setup_zmq_socket(
            mission_sock,
            'internal.streams.mission_telemetry',
            SocketOperation.CONNECT
            )
        return InputProducer(
                self._base_producer(
                    mission_sock,
                    MissionTelemetry(),
                    gabriel_pb2.PayloadType.TEXT
                    ),
                [],
                source_name="mission_telemetry"
                )

    def process(self, result_wrapper):
        '''
        Send results from Gabriel over the result socket.
        '''
        if len(result_wrapper.results) != 1:
            return
        self._result_sock.send_multipart([
            result_wrapper.result_producer_name.value.encode('utf-8'),
            result_wrapper.SerializeToString()
            ])
    
    def _base_producer(self, socket, proto_class, payload_type):
        '''
        Returns a base producer object that builds a given payload type
        off a corresponding socket.
        '''
        async def producer():
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = payload_type
            try:
                _, data = await socket.recv_multipart()  
            except Exception as e:
                return input_frame
            proto_class.ParseFromString(data)
            input_frame.extras.Pack(proto_class)
            return input_frame
        return producer
