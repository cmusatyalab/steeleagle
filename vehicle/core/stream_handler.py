import asyncio
import zmq
import zmq.asyncio
import time
import datetime
# Utility import
from util.config import query_config
from util.sockets import setup_zmq_socket, SocketOperation
from util.log import get_logger
# Gabriel import
from gabriel_client.zeromq_client import ProducerWrapper, ZeroMQClient
from gabriel_protocol import gabriel_pb2
from gabriel_server import cognitive_engine
# Protocol import
from python_bindings.telemetry_pb2 import DriverTelemetry, Frame, MissionTelemetry
from python_bindings.result_pb2 import ComputeResult

logger = get_logger('core/stream_handler')

class StreamHandler:
    '''
    Pushes telemetry and imagery to both local compute and remote compute
    servers and relays results over the result socket.
    '''
    def __init__(self, law_authority):
        # Reference to the law authority
        self.law_authority = law_authority
        # Subscribe to all telemetry/result sockets
        self._driver_sock = zmq.asyncio.Context().socket(zmq.SUB)
        setup_zmq_socket(
            self._driver_sock,
            'internal.streams.driver_telemetry',
            SocketOperation.CONNECT
            )
        self._imagery_sock = zmq.asyncio.Context().socket(zmq.SUB)
        setup_zmq_socket(
            self._imagery_sock,
            'internal.streams.imagery',
            SocketOperation.CONNECT
            )
        self._mission_sock = zmq.asyncio.Context().socket(zmq.SUB)
        setup_zmq_socket(
            self._mission_sock,
            'internal.streams.mission_telemetry',
            SocketOperation.CONNECT
            )
        # Create the result socket
        self._result_sock = zmq.asyncio.Context().socket(zmq.PUB)
        setup_zmq_socket(
            self._result_sock,
            'internal.streams.results',
            SocketOperation.BIND
            )
        # Handler for remote compute queries
        producers = [
            self.get_driver_telemetry_producer(),
            self.get_imagery_producer(),
            self.get_mission_telemetry_producer()
        ]
        #lc_server = \
        #    query_config('internal.streams.local_compute').replace('unix', 'ipc')
        #self._local_compute_handler = LocalComputeHandler(lc_server, None, producers, self.process, ipc=True)
        #self._lch_task = None
        rc_server, rc_port = \
            query_config('cloudlet.remote_compute_service').split(':')
        self._remote_compute_handler = RemoteComputeHandler(rc_server, rc_port, producers, self.process)
        self._rch_task = None

    async def start(self):
        #self._lch_task = asyncio.create_task(self._local_compute_handler.launch_async())
        self._rch_task = asyncio.create_task(self._remote_compute_handler.launch_async())

    async def wait_for_termination(self):
        #await asyncio.gather(self._lch_task, self._rch_task)
        await self._rch_task

    def get_driver_telemetry_producer(self):
        async def producer():
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.OTHER
            data = await self._driver_sock.recv()
            message = DriverTelemetry()
            input_frame.extras.Pack(message.ParseFromString(data))
            return input_frame
        return ProducerWrapper(producer=producer, source_name="driver_telemetry")
    
    def get_imagery_producer(self):
        async def producer():
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.IMAGE
            data = await self._driver_sock.recv()
            message = DriverTelemetry()
            input_frame.extras.Pack(message.ParseFromString(data))
            return input_frame
        return ProducerWrapper(producer=producer, source_name="imagery")
    
    def get_mission_telemetry_producer(self):
        async def producer():
            input_frame = gabriel_pb2.InputFrame()
            input_frame.payload_type = gabriel_pb2.PayloadType.OTHER
            data = await self._driver_sock.recv()
            message = DriverTelemetry()
            input_frame.extras.Pack(message.ParseFromString(data))
            return input_frame
        return ProducerWrapper(producer=producer, source_name="mission_telemetry")
                
    async def process(self, result_wrapper):
        if len(result_wrapper.results) != 1:
            return

        response = cognitive_engine.unpack_extras(
            control_protocol.Response, result_wrapper
        )
        for result in result_wrapper.results:
            self._result_sock.send(result.payload)

class LocalComputeHandler(ZeroMQClient):
    def __init__(self, server, port, producer_wrappers, consumer):
        super().__init__(server, port, producer_wrappers, consumer)

    def set_offload_strategy(self):
        pass

class RemoteComputeHandler(ZeroMQClient):
    def __init__(self, server, port, producer_wrappers, consumer):
        super().__init__(server, port, producer_wrappers, consumer)

    def set_offload_strategy(self):
        pass
