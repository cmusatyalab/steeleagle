import asyncio
import logging

import zmq
from util.utils import SocketOperation, setup_socket

logger = logging.getLogger(__name__)


class StubResponse:
    def __init__(self):
        self.event = asyncio.Event()
        self.permission = False
        self.result = None

    def put_result(self, result):
        self.result = result

    def get_result(self):
        return self.result

    async def wait(self):
        await self.event.wait()

    def set(self):
        self.event.set()


class Stub:
    def __init__(self, socket_identity, socket_endpoint, stub_type):
        self.seq_num = 1
        self.request_map = {}

        context = zmq.Context()
        self.sock = context.socket(zmq.DEALER)
        self.sock.setsockopt(zmq.IDENTITY, socket_identity)
        setup_socket(self.sock, SocketOperation.CONNECT, socket_endpoint)
        self.stub_type = stub_type

    def sender(self, request, stub_response):
        seq_num = self.seq_num
        logger.debug(f"type: {self.stub_type} Sending request with seq_num: {seq_num}")
        request.seq_num = seq_num
        self.seq_num += 1
        self.request_map[seq_num] = stub_response

        serialized_request = request.SerializeToString()
        self.sock.send_multipart([serialized_request])

    def parse_response(self, response_parts, response_type):
        response = response_type()
        response.ParseFromString(response_parts[0])

        stub_response = self.request_map.get(response.seq_num)
        if not stub_response:
            logger.error(f"type: {self.stub_type} Unknown seq_num: {response.seq_num}")
            return
        stub_response.put_result(response)
        stub_response.set()

        del self.request_map[response.seq_num]

    async def receiver_loop(self, parse_response_callback):
        while True:
            try:
                response_parts = self.sock.recv_multipart(flags=zmq.NOBLOCK)
                parse_response_callback(response_parts)
            except zmq.Again:
                pass
            except Exception as e:
                logger.error(f"type: {self.stub_type} Failed to parse message: {e}")
                break
            await asyncio.sleep(0)

    async def send_and_wait(self, request):
        try:
            stub_response = StubResponse()
            self.sender(request, stub_response)
            try:
                await asyncio.wait_for(stub_response.wait(), 10)
            except (TimeoutError, asyncio.TimeoutError):
                del self.request_map[request.seq_num]
                return None
            reply = stub_response.get_result()
            return reply
        except Exception as e:
            logger.error(e)
            return None
