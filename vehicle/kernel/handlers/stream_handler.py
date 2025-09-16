import asyncio
import zmq
import zmq.asyncio
import time
# Utility import
from util.config import query_config
from util.sockets import setup_zmq_socket, SocketOperation
from util.log import get_logger
# Gabriel import
from gabriel_client.zeromq_client import ProducerWrapper, ZeroMQClient
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine
# Protocol import
from steeleagle_sdk.protocol.messages.telemetry_pb2 import DriverTelemetry, Frame, MissionTelemetry
from steeleagle_sdk.protocol.messages.result_pb2 import ComputeResult

logger = get_logger('kernel/handlers/stream_handler')

class StreamHandler:
    '''
    Pushes telemetry and imagery to both local compute and remote compute
    servers and relays results over the result socket.
    '''
    def __init__(self, law_authority):
        # Reference to the law authority
        self.law_authority = law_authority
        # Create the result socket
        self._result_sock = zmq.asyncio.Context().socket(zmq.PUB)
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
            producers = [
                self.get_driver_telemetry_producer(),
                self.get_imagery_producer(),
                self.get_mission_telemetry_producer()
            ]
            lc_server = \
                query_config('internal.streams.local_compute').replace('unix', 'ipc')
            self._local_compute_handler = ShapedComputeHandler(lc_server, None, producers, self.process, ipc=True)
        except zmq.error.ZMQError:
            logger.warning('No valid configuration found for local compute handler, not running it')
            self._local_compute_handler = None
        # Configure remote compute handler
        self._remote_compute_handler = None
        self._rch_task = None
        try:
            # Create producers
            producers = [
                self.get_driver_telemetry_producer(),
                self.get_imagery_producer(),
                self.get_mission_telemetry_producer()
            ]
            rc_server, rc_port = \
                query_config('cloudlet.remote_compute_service').split(':')
            self._remote_compute_handler = ShapedComputeHandler(rc_server, rc_port, producers, self.process)
        except zmq.error.ZMQError:
            logger.warning('No valid configuration found for remote compute handler, not running it')
            self._remote_compute_handler = None

    async def start(self):
        if self._local_compute_handler:
            self._lch_task = asyncio.create_task(self._local_compute_handler.launch_async())
        else:
            self._lch_task = asyncio.sleep(0) # Default task so gather does not cause an exception
        if self._remote_compute_handler:
            self._rch_task = asyncio.create_task(self._remote_compute_handler.launch_async())
        else:
            self._rch_task = asyncio.sleep(0)

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
        return ProducerWrapper(
                producer=self._base_producer(
                    driver_sock,
                    DriverTelemetry(),
                    gabriel_pb2.PayloadType.OTHER
                    ),
                source_name="telemetry"
                )
    
    def get_imagery_producer(self):
        imagery_sock = zmq.asyncio.Context().socket(zmq.SUB)
        imagery_sock.setsockopt(zmq.SUBSCRIBE, b'')
        setup_zmq_socket(
            imagery_sock,
            'internal.streams.imagery',
            SocketOperation.CONNECT
            )
        return ProducerWrapper(
                producer=self._base_producer(
                    imagery_sock,
                    Frame(),
                    gabriel_pb2.PayloadType.IMAGE
                    ),
                source_name="telemetry"
                )
    
    def get_mission_telemetry_producer(self):
        mission_sock = zmq.asyncio.Context().socket(zmq.SUB)
        mission_sock.setsockopt(zmq.SUBSCRIBE, b'')
        setup_zmq_socket(
            mission_sock,
            'internal.streams.mission_telemetry',
            SocketOperation.CONNECT
            )
        return ProducerWrapper(
                producer=self._base_producer(
                    mission_sock,
                    MissionTelemetry(),
                    gabriel_pb2.PayloadType.OTHER
                    ),
                source_name="telemetry"
                )

    def process(self, result_wrapper):
        if len(result_wrapper.results) != 1:
            return
        asyncio.create_task(self._result_sock.send_multipart([
                result_wrapper.result_producer_name.value.encode('utf-8'),
                result_wrapper.SerializeToString()
                ]))

    def set_offload_strategy(self, strategy):
        pass
    
    def _base_producer(self, socket, proto_class, payload_type):
        async def producer():
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = payload_type
            try:
                _, data = await socket.recv_multipart()
            except Exception as e:
                # NOTE: At some point, we want to report something here
                return input_frame
            proto_class.ParseFromString(data)
            input_frame.extras.Pack(proto_class)
            return input_frame
        return producer

class ShapedComputeHandler(ZeroMQClient): 
    '''
    A variant of the Gabriel ZeroMQ client that allows for offload shaping 
    by setting an offload strategy.
    '''
    def __init__(self, server, port, producer_wrappers, consumer, ipc=False):
        super().__init__(server, port, producer_wrappers, consumer, ipc=ipc)

    def set_strategy(self):
        # TODO: Needs to be implemented!
        pass
